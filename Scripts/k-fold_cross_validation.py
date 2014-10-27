#!usr/bin/env python2.7
# John Vivian

'''
This script will perform k-fold cross-validation with our training set of JSON events (230). 


1. Randomize 230 events into 5 groups of 46 events
2. For every group: train on the other 4 sets
3. Read in HMM, Train
4. Test on the withheld group
3. Return Hard and Softcalls for each method:
    F_h, F_s, L_h, L_s, ... ( Method_hard/soft )
4. Store in array (5,12)
5. Output results.

6. Meta: Store each array in a dictionary / 3d array for different filter scores.


Currently on:  Step 6

'''

import sys, os, random, argparse
import numpy as np
import Methods

parser = argparse.ArgumentParser(description='Can run either simple or substep model')
parser.add_argument('-s','--substep', action='store_true', help='Imports substep model instead of simple')
args = vars(parser.parse_args())

sys.path.append( '../Models' )
if args['substep']:
    print '\n-=SUBSTEP=-'
    from Substep_Model import *
else:
    print '\n-=SIMPLE=-'
    from Simple_Model import *


## 1. Randomize 230 events into 5 groups of 46 events

# Find JSON Events 
source = '../Data/JSON'
for root, dirnames, filenames in os.walk(source):
    events = filenames
    
# Randomize List
random.shuffle( events )

# Break into 5 equal groups
events = [ events[i::5] for i in xrange(5) ]
    
## 2. For every group: withold and train on other 4. 
# Create array
data = np.zeros( (5, 12) ) 

## This would be the place to do another iteration by filter score: 
#cscore = 0.9
cscores = [ 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1 ]
for cscore in cscores:
    counters = []
    for i in xrange(5):
        counter = 0
        
        # Separate into Training and Test sets.
        test = events[i]
        training = [x for x in events if x != test]
        
        # Convert training set into sequences
        sequences = []
        for group in training:
            for event in group:
                event = Event.from_json( '../Data/JSON/' + event )
                means = [seg['mean'] for seg in event.segments]
                sequences.append( means )
        
        ## 3. Read in Untrained HMM then train
        with open ( '../Data/HMMs/untrained.txt', 'r' ) as file:
            model = Model.read( file ) 
        print '\nTraining HMM: Witholding group {}. Training size {}'.format( i+1, len(training) )
        model.train( sequences )

        ## 4. Test on the withheld group
        # Acquire indices
        indices = { state.name: i for i, state in enumerate( model.states ) }
        # Bins to hold counts
        bins = { 'f': 0, 'l': 0, 'r':0, 'b': 0, 'i': 0, 'h': 0 }                # Counter for hard calls
        soft_calls = { 'f': [], 'l': [], 'r':[], 'b': [], 'i': [], 'h': [] }    # Will hold soft calls
        for event in test:
       
            # Convert JSON to event
            event = Event.from_json( '../Data/JSON/' + event )
            
            # Convert event into a list of means
            means = [seg['mean'] for seg in event.segments]
           
            # Perform forward_backward algorithm
            trans, ems = model.forward_backward( means )
           
            # Partition the event into 'chunks' of context / label regions
            contexts, labels = partition_event( indices, event, ems, means)

            # Get chunk scores
            contexts, labels = chunk_score( indices, contexts, labels, ems )
           
            # Get chunk vector
            contexts, labels = chunk_vector( indices, contexts, labels, ems )
            
            contexts = [ x for x in contexts if x[0] >= cscore ]     
            labels = [ x for x in labels if x[0] >= cscore ]
            
            if len(contexts) > 0 and len(labels) > 0:       ## For this analysis, there must be greater than 2 contexts
                counter += 1
                ## Single Read Methods
                fchunk, fcall = Methods.first_chunk( contexts, labels, cscore )
                lchunk, lcall = Methods.last_chunk( contexts, labels, cscore )
                rchunk, rcall = Methods.random_chunk( contexts, labels, cscore )
                
                ## Multi-Read Methods
                bchunk, bcall = Methods.best_chunk( contexts, labels )
                ichunk, icall = Methods.ind_consensus( contexts, labels, cscore )
                hchunk, hcall = Methods.hmm_consensus( indices, ems, len(means), chunk_vector )

                #print '-=Single Read Methods=-'
                #print 'First Chunk: {:<11} Hard Call: {:<4}, Label: {}'.format( round(fchunk,4), fcall[0], fcall[1] )
                soft_calls['f'].append( fchunk )
                if fcall[0] == fcall[1]:
                    bins['f'] += 1

                #print 'Last Chunk: {:<11} Hard Call: {:<4}, label: {}'.format( round(lchunk,4), lcall[0], lcall[1] )
                soft_calls['l'].append( lchunk )
                if lcall[0] == lcall[1]:
                    bins['l'] += 1
                    
                #print 'Random Chunk: {:<11} Hard Call: {:<4}, Label: {}'.format( round(rchunk,4), rcall[0], rcall[1] )
                soft_calls['r'].append( rchunk )
                if rcall[0] == rcall[1]:
                    bins['r'] += 1
                
                #print '-=Multi-Read Methods=-'
                #print 'Best Chunk: {:<11} Hard Call: {:<4}, Label: {}'.format( round(bchunk,4), bcall[0], bcall[1] )
                soft_calls['b'].append( bchunk )
                if bcall[0] == bcall[1]:
                    bins['b'] += 1
                    
                #print 'Ind Consensus: {:<11} Hard Call: {:<4}, Label: {}'.format( round(ichunk,4), icall[0], icall[1] ) 
                soft_calls['i'].append( ichunk )
                if icall[0] == icall[1]:
                    bins['i'] += 1
                    
                #print 'HMM Consensus: {:<11} Hard Call: {:<4}, Label: {}'.format( round(hchunk,4), hcall[0], hcall[1] ) 
                soft_calls['h'].append( hchunk )
                if hcall[0] == hcall[1]:
                    bins['h'] += 1
                    
        ## Add results to array
        if counter > 0:
            data[i][0] = bins['f']*1.0 / counter
            data[i][1] = np.mean(soft_calls['f'])
            data[i][2] = bins['l']*1.0 / counter
            data[i][3] = np.mean(soft_calls['l'])
            data[i][4] = bins['r']*1.0 / counter
            data[i][5] = np.mean(soft_calls['r'])
            data[i][6] = bins['h']*1.0 / counter
            data[i][7] = np.mean(soft_calls['h'])
            data[i][8] = bins['b']*1.0 / counter
            data[i][9] = np.mean(soft_calls['b'])
            data[i][10] = bins['i']*1.0 / counter
            data[i][11] = np.mean(soft_calls['i'])
        
        print counter
        counters.append( counter )
        
    print '\n', data, '\nSample Size: ~{}'.format( np.mean(counters) )

    np.savetxt( '../Data/Results/1chunk_' + str(np.floor(np.mean(counters))) \
                + '_cscore_'+ str(cscore).split('.')[1] + '.txt', data, delimiter = ',' )