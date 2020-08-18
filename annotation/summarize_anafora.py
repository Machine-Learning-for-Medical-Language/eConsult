
import anafora
from anafora.select import Select

import os
import sys
from os.path import join

import csv

def main(args):

    TYPE = 'Annotation type'
    ROWID = 'Row Id'
    STATUS = 'Status'
    ANNOTATOR = 'Annotator'
    LABEL = 'Label'
    SPAN_TEXT = 'Span text'
    ANNOT_TEXT = 'Annotated text'

    if len(args) < 4:
        sys.stderr.write('2 required arguments: <input anafora dir> <output csv file> <Prob label> <Type label>\n')
        sys.exit(-1)

    PROB_TEXT = args[2]
    TYPE_TEXT = args[3]
    
    with open(args[1], 'w', newline='') as csvfile:
        # fieldnames=['Annotation type', 'row_id', 'Status', 'Annotator', 'Label', 'Span text', 'Annotated text']
        fieldnames=[TYPE, ROWID, STATUS, ANNOTATOR, LABEL, SPAN_TEXT, ANNOT_TEXT]
        csvout = csv.DictWriter(csvfile, fieldnames, delimiter=',', quotechar='"')
        csvout.writeheader()
        
        for sub_dir, text_name, xml_names in anafora.walk(args[0]):
            if len(xml_names) == 0:
                continue

            with open( join( join(args[0], sub_dir), text_name), 'r') as tf:
                text = tf.read()

            for xml_name in xml_names:
                xml_path = os.path.join(args[0], sub_dir, xml_name)
                xml_parts = xml_name.split('.')
                annotator = xml_parts[2]
                status = xml_parts[3]
                data = anafora.AnaforaData.from_file(xml_path)

                for annot in data.annotations.select_type(PROB_TEXT):
                    span = annot.spans[0]
                    span_text = text[span[0]:span[1]]
                    cat = annot.properties['Content']
                    annotated_text = text[:span[0]] + '<problem> ' + span_text + ' </problem>' + text[span[1]:]
                    csvout.writerow({TYPE:'Problem', 
                                     ROWID:sub_dir, 
                                     STATUS:status, 
                                     ANNOTATOR:annotator, 
                                     LABEL:cat, 
                                     SPAN_TEXT:span_text, 
                                     ANNOT_TEXT: annotated_text})

                for annot in data.annotations.select_type(TYPE_TEXT):
                    span = annot.spans[0]
                    span_text = text[span[0]:span[1]]
                    cat = annot.properties['Type']
                    annotated_text = text[:span[0]] + '<type> ' + span_text + ' </type>' + text[span[1]:]
                    csvout.writerow({TYPE:'Type', 
                                     ROWID:sub_dir, 
                                     STATUS:status, 
                                     ANNOTATOR:annotator, 
                                     LABEL:cat, 
                                     SPAN_TEXT:span_text, 
                                     ANNOT_TEXT: annotated_text})

if __name__ == '__main__':
    main(sys.argv[1:])

