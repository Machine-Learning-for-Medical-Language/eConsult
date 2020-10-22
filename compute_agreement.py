#!/usr/bin/env python

import sys

import csv
from sklearn.metrics import cohen_kappa_score

def main(args):
    if len(args) < 1:
        sys.stderr.write('One required argument: <csv file>\n')
        sys.exit(-1)

    annot1 = 'dave'
    annot2 = 'mbarnett'

    csv_path = args[0]

    # A dictionary that maps from econsult row ids to a dictionary of annotators, and
    # the dictionary of annotators maps from annotator id to a dictionary of annotation type to
    # a dictionary of label=>span_text
    # so to get the list of labels for a row by an annotator we do annots[row_id][annotator][annot_type].keys()
    annots = {}
    
    with open(csv_path, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        for row in reader:
            annot_type, row_id, annot_status, annotator, label, span_text, full_text = row
            if not row_id in annots:
                annots[row_id] = {}
            annot = annots[row_id]
            if not annotator in annot:
                annot[annotator] = {}
            if not annot_type in annot[annotator]:
                annot[annotator][annot_type] = {}
            annot[annotator][annot_type][label] = span_text

    # get cohen's kappa for each question type annotation
    for q_type in ['Diagnosis/management', 'Procedure-Other', 'Procedure-Colonoscopy', 'Procedure-EGD', 'Procedure-FlexSig']:
        annot1_labels = []
        annot2_labels = []
        
        for row_id in annots.keys():
            if len(annots[row_id].keys()) < 2:
                continue
            
            try:
                val = annots[row_id][annot1]['Type'][q_type]
                # if this worked then they made an annotation of this type for this row
                annot1_labels.append(1)
            except:
                annot1_labels.append(0)
            
            try:
                val = annots[row_id][annot2]['Type'][q_type]
                annot2_labels.append(1)
            except:
                annot2_labels.append(0)
        
        kappa = cohen_kappa_score(annot1_labels, annot2_labels)
        print("Kappa for type %s is %f" % (q_type, kappa))
        
    # Get the accuracy/f1 score
    skipped = 0
    counted = 0
    PROB = "Problem"
    TYPE = "Type"
    acc_points = {PROB: 0, TYPE: 0}
    rec_denom = {PROB: 0, TYPE: 0}
    prec_denom = {PROB: 0, TYPE: 0}

    for row_id in annots.keys():
        annotators = list(annots[row_id].keys())
        if len(annotators) != 2:
            skipped += 1
            # sys.stderr.write('Row %s does not have 2 annotators, it has %d\n' % (row_id, len(annotators)))
            continue

        if not annot1 in annotators or not annot2 in annotators:
            sys.stderr.write("unrecognized annotator in list of annotators, skipping row %s" % (row_id))
            skipped += 1
            continue

        counted += 1

        if TYPE in annots[row_id][annot1]:
            annot1_type_labels = set(annots[row_id][annot1][TYPE].keys())
        else:
            sys.stderr.write("No TYPE annotations in row %s for annotator %s\n" % (row_id, annot1))
            annot1_type_labels = set([])

        if TYPE in annots[row_id][annot2]:
            annot2_type_labels = set(annots[row_id][annot2][TYPE].keys())
        else:
            sys.stderr.write("No TYPE annotations in row %s for annotator %s\n" % (row_id, annot2))
            annot2_type_labels = set([])

        
        type_overlap_size = len(annot1_type_labels.intersection(annot2_type_labels))
        if type_overlap_size == 0:
            type_row_prec = type_row_rec = 0.0
        else:
            type_row_prec = type_overlap_size / len(annot1_type_labels)
            type_row_rec = type_overlap_size / len(annot2_type_labels)

        acc_points[TYPE] += type_overlap_size
        rec_denom[TYPE] += len(annot1_type_labels)
        prec_denom[TYPE] += len(annot2_type_labels)

#        if type_row_prec < 1.0 or type_row_rec < 1.0:
#            print("TYPE P/R for row id %s: %f/%f (details: %d overlap, %s: %d annots, %s: %d annots)" % (row_id, type_row_prec, type_row_rec, type_overlap_size, annot1, len(annot1_type_labels), annot2, len(annot2_type_labels)))

        annot1_prob_labels = set(annots[row_id][annot1][PROB].keys())
        annot2_prob_labels = set(annots[row_id][annot2][PROB].keys())

        prob_overlap_size = len(annot1_prob_labels.intersection(annot2_prob_labels))
        prob_row_prec = prob_overlap_size / len(annot1_prob_labels)
        prob_row_rec = prob_overlap_size / len(annot2_prob_labels)

        acc_points[PROB] += prob_overlap_size
        rec_denom[PROB] += len(annot1_prob_labels)
        prec_denom[PROB] += len(annot2_prob_labels)

#        if prob_row_prec < 1.0 or prob_row_rec < 1.0:
#            print('PROBLEM P/R for row id %s: %f/%f (details: %d overlap, %s: %d annots, %s: %d annots)'% (row_id,
#            prob_row_prec, prob_row_rec, prob_overlap_size, annot1, len(annot1_prob_labels), annot2, len(annot2_prob_labels)))


    global_type_rec = acc_points[TYPE] / rec_denom[TYPE]
    global_type_prec = acc_points[TYPE] / prec_denom[TYPE]
    global_type_f1 = 2 * global_type_prec* global_type_rec / (global_type_prec+global_type_rec)

    global_prob_rec = acc_points[PROB] / rec_denom[PROB]
    global_prob_prec = acc_points[PROB] / prec_denom[PROB]
    global_prob_f1 = 2 * global_prob_rec * global_prob_prec / (global_prob_prec+global_prob_rec)

    print("Found %d documents with 2 annotations, skipped %d documents with !=2 annotations" % (counted, skipped))
    print("Global type P/R/F: %f\t%f\t%f" % (global_type_prec, global_type_rec, global_type_f1))
    print("Global prob P/R/F: %f\t%f\t%f" % (global_prob_prec, global_prob_rec, global_prob_f1))


if __name__ == '__main__':
    main(sys.argv[1:])