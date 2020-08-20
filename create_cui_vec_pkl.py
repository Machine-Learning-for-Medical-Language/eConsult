#!python3
import sys
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
import pickle
from tqdm import tqdm
import sqlite3

def cui_tokenizer(s):
    return s.split()

def main(args):
    if len(args) < 2:
        sys.stderr.write('2 required arguments: <sqlite file> <vectorizer pkl file> [year]\n')
        sys.exit(-1)

    conn = sqlite3.connect(args[0])
    c = conn.cursor()
    
    note_ids = []
    for row in c.execute('select note_id from NOTE'):
        note_ids.append(row[0])
    
    data = []
    
    for note_id in note_ids:
        cuis = []
        for row in c.execute('select note_nlp_concept from NOTE_NLP where note_id=?', (note_id,)):
            cuis.append(row[0])
        data.append(' '.join(cuis))
      
    tfidf_vectorizer = TfidfVectorizer(max_df=0.95,
                                       min_df=2,
                                       preprocessor=None,
                                       tokenizer=None,
                                      )
    
    print("Fitting tfidf vectorizer and transforming data")
    tfidf = tfidf_vectorizer.fit_transform(data)
    
    print("Writing vectorizer to filename %s" % (args[1]))
    output = (tfidf, tfidf_vectorizer, note_ids)
    with open(args[1], 'wb') as tv:
        pickle.dump(output, tv)
           
if __name__ == '__main__':
    main(sys.argv[1:])

