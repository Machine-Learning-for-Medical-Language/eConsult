import os, sys, csv
import random
from data.econsult_data import get_text_for_row

def main(args):
    if len(args) < 3:
        sys.stderr.write('Required arguments: <econsult source directory> <gold csv file> <output csv file>\n')
        sys.exit(-1)
        
    annotated_rows = set()
    
    with open(args[1], 'rt') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row[1] == 'Row Id':
                continue
                
            row_id = int(row[1])
            annotated_rows.add(row_id)
            
    
    with open(args[2], 'wt') as of:
        writer = csv.writer(of)
        sample_rows = set(random.sample(annotated_rows, 200))
        err_count = 0
        for row_id in sample_rows:
            text = get_text_for_row(args[0], row_id)
            if text is None:
                err_count += 1
                sys.stderr.write("Could not find file corresponding to row %d\n" % (row_id) )

                if err_count > 10:
                    sys.stderr.write("aborting early due to multiple missing files\n")
                    break
            else:
                writer.writerow([row_id, text])
            
if __name__ == '__main__':
    main(sys.argv[1:])
