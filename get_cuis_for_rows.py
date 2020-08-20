import sys, os
import csv, sqlite3

def main(args):
    if len(args) < 2:
        sys.stderr.write('Required arguments: <input sql file> <input csv>\n')
        sys.exit(-1)
    
    sql_fn, csv_fn = args
    
    conn = sqlite3.connect(sql_fn)
    c = conn.cursor()

    with open(csv_fn, 'rt') as csv_file:
        reader = csv.reader(csv_file);
        for row_ind, row in enumerate(reader):
            if row_ind == 0:
                # first row is the headers
                continue
                
            _, row_id, _, _ = row
            row_id = int(row_id)
            
            # get all the cuis for this text
            all_cuis = []
            for cui in c.execute('SELECT note_nlp_concept from NOTE_NLP where note_id=?', (row_id,) ):
                all_cuis.append(cui[0])
            
            cui_count = len(all_cuis)
            uniq_cui_count = len(set(all_cuis))
            
            print('%d,%d,%d' % (row_id, cui_count, uniq_cui_count))            
            #if row_ind >= 100:
                #break

if __name__ == '__main__':
    main(sys.argv[1:])

