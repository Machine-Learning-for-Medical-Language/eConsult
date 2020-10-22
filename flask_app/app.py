import sys
import json
import logging
import datetime
from dateutil import parser
import time

from flask import Flask, render_template, current_app, g, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as cos
import numpy as np
import pickle

import sqlite3
import ctakes_rest

app = Flask(__name__)
conn = None
cur = None

with open('2008-vectors.pkl', 'rb') as vf:
    (vectors, vectorizer, vector_files) = pickle.load(vf)

with open('ohdsi-cui-vectors.pkl', 'rb') as cvf:
    (cui_vecs, cui_vectorizer, note_ids) = pickle.load(cvf)

logging.basicConfig(level=logging.INFO)

age_ranges = ['Infant', 'Child', 'Teenager', 'Adult', 'Geriatric']

def age_to_range(age):
    if age < 3:
        return age_ranges[0]
    elif age < 13:
        return age_ranges[1]
    elif age < 20:
        return age_ranges[2]
    elif age < 65:
        return age_ranges[3]
    else:
        return age_ranges[4]

def get_flows_db():
    if 'flows' not in g:
        g.flows = sqlite3.connect('../sql/ym_flows.sql')
    return g.flows

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('../sql/liver+gastro_2010-2017.sql')
    return g.db

def get_triage_db():
    if 'triage' not in g:
        g.triage = sqlite3.connect('../sql/ym_triage.sql')
    return g.triage

def get_ohdsi_db():
    if 'ohdsi' not in g:
        g.ohdsi = sqlite3.connect('../sql/ohdsi.sql')
    return g.ohdsi

# def close_db(e=None):
#     db = g.pop('db', None)

#     if db is not None:
#         db.close()
@app.teardown_appcontext
def close_db(e=None):

    db = g.pop('db', None)
    if db is not None:
        db.close()

    flows = g.pop('flows', None)
    if flows is not None:
        flows.close()
    
    triage = g.pop('triage', None)
    if triage is not None:
        triage.close()
        
    ohdsi = g.pop('ohdsi', None)
    if ohdsi is not None:
        ohdsi.close()

specialties = ["Allergy", "Cardiac/Other Testing", "Cardiology", "CardiothoracicSurgery", "Dental", "Dermatology", "Endocrine", "ENT", "Gastroenterology", "GeneralSurgery", "Geriatrics", "Heme/Onc", "ID", "Neurology", "Neurosurgery", "OB/Gyn", "Opthalmology", "OrthopaedicSurgery", "Pain", "PlasticSurgery", "PM&R", "Podiatry", "Procedure", "Psychiatry", "Pulmonary", "Radiology", "Renal", "Rheumatology", "Sleep", "Urology", "VascularSurgery"]

@app.route('/similarity', methods=['POST', 'GET'])
def similarity():
    responses = []
    if request.method == 'POST':
        # process form
        logging.info(request.form)
        question = request.form.get('question')
        specialty = request.form.get('specialty')
        
        logging.info("Received question with specialty %s" % (specialty))
        logging.info("Received question starting with %s" % (question[:50]))
        
        request_vector = vectorizer.transform([question])
        similarities = cos(request_vector, vectors)[0]
        ranks = np.argsort(similarities).tolist()
        ranks.reverse()
        
        for ind in range(5):
            doc_ind = ranks[ind]
            filename = vector_files[doc_ind]
            with open(filename, 'r') as note_file:
                note_text = '\n'.join(note_file.readlines())
            
            responses.append({'text':note_text, 'sim':similarities[doc_ind]})
            
    return render_template('similarity.html', specialties=specialties, responses=responses)

@app.route('/cui_sim', methods=['POST', 'GET'])
def cui_similarity():
    responses = []
    question_cuis = {}
    
    ohdsi = get_ohdsi_db().cursor()
    
    if request.method == 'POST':
        logging.info(request.form)

        begin_time = time.time()

        question = request.form.get('question')
        specialty_filter = request.form.get('specialty')
        age_filter = request.form.get('age')
        cui_filter = request.form.get('qcui')
        logging.debug("Saw request with cui value %s" % (cui_filter,))
        
        processed_query = ctakes_rest.process_sentence(question)
        
        for cui, start, end in processed_query:
            question_cuis[cui] = question[start:end]
        
        end_time = time.time()
        logging.info("Processing input with ctakes rest required %f s" % (end_time-begin_time))

        begin_time = end_time

        cui_text = ' '.join([x[0] for x in processed_query])
        cui_vector = cui_vectorizer.transform([cui_text])
        similarities = cos(cui_vector, cui_vecs)[0]
        ranks = np.argsort(similarities).tolist()
        ranks.reverse()
        end_time = time.time()
        logging.info("Vectorizing and computing cos similarity took %f s" % (end_time-begin_time))
        
        for ind in range(100):
            doc_ind = ranks[ind]
            note_id = note_ids[doc_ind]

            begin_time = time.time()
            ## This is what's slow:
            #ohdsi.execute('select note_text, note_type, note_date, person.year_of_birth from NOTE INNER JOIN PERSON on note.person_id=person.person_id where note_id=?', (note_id,))
            ## This is quite a bit faster but still the bottleneck since it's in the loop. Maybe can fix with some kind of better index?
            ohdsi.execute('select note_text, note_type, note_date, person_id from NOTE where note_id=?', (note_id,))
                
            note_text, specialty, note_date, person_id = ohdsi.fetchone()

            end_time = time.time()
            logging.debug("Finding note from note_id took %f s" % (end_time-begin_time))
            begin_time = end_time

            ohdsi.execute('select year_of_birth from PERSON where person_id=?', (person_id,))
            yob = ohdsi.fetchone()[0]

            # note_year = datetime.datetime.strptime(note_date, '%d/%m/%Y %H:%M').year
            note_year = parser.parse(note_date).year
            note_age = note_year - yob
            age_range = age_to_range(note_age)
            end_time = time.time()
            logging.debug("Finding yob from person table took %f s" % (end_time-begin_time))
            begin_time = end_time

            if specialty != specialty_filter and specialty_filter != 'All':
                continue

            if age_range != age_filter and age_filter != 'All':
                continue
            
            ohdsi.execute('select content_type from question_content where note_id=?', (note_id,))
            contents = [x[0] for x in ohdsi]
            end_time = time.time()
            logging.debug("Selecting content type took %f s" % (end_time-begin_time))
            begin_time = end_time

            ohdsi.execute('select note_nlp_concept from note_nlp where note_id=?', (note_id,))
            cuis = set([x[0] for x in ohdsi])
            if not cui_filter is None and cui_filter != '' and not cui_filter in cuis:
                continue

            cuis = cuis.intersection(set(question_cuis.keys()))
            responses.append({'text': note_text, 'cuis':' '.join(cuis), 'sim':similarities[doc_ind], 'specialty':specialty, 'contents':', '.join(contents)})

            end_time = time.time()
            logging.debug("Finding concepts in note took %f s" % (end_time - begin_time))

            if len(responses) > 10:
                break

    
    return render_template('cui_sim.html', question_cuis=question_cuis, specialties=specialties, responses=responses)

@app.route('/', methods=['POST', 'GET'])
@app.route('/index', methods=['POST', 'GET'])
def flows():
    return render_template('flows.html', data=flows_data())

@app.route("/flows", methods=['POST'])
def flows_data():
    cur = get_flows_db().cursor()
    
    start_my = request.form.get('startMonthYear', default='2017-12')
    if start_my == '':
        start_my = '2017-12'
    
    year, month = [int(x) for x in start_my.split('-')]
    
    logging.info('Received request for flows from year %d and month %02d' % (year, month))
    
    data = []
    cur.execute('select * from flows where date=="%4d-%02d"' % (year, month))
    for row in cur:
        ## don't need the 0th column because it will all be the start_my passed in:
        ## and skip really rare patterns
        if row[3] > 20:
            data.append([row[1], row[2], row[3]])
    
    logging.info("Returning %d rows of data" % (len(data)))
    
    return {'data': data}

@app.route("/counts")
def counts():

    cur = get_db().cursor()
    rows = []
    for year in range(2010, 2017+1):
        for month in range(1, 13):
            year_size = len(cur.execute("select * from econsults where date(date) between date('%4d-%02d-01') and date('%4d-%02d-31')" % (year, month, year, month)).fetchall())
            rows.append({'Date': '%4d-%02d' % (year, month),
                            'Count': year_size})

    cur.close()
    data = {'chart_data':rows}
    return render_template('counts.html', data=data)

@app.route("/cuis", methods=['GET', 'POST'])
@app.route("/tracker", methods=['GET', 'POST'])
def tracker():
    start_my = request.form.get('startMonthYear', default='2010-01')
    end_my = request.form.get('endMonthYear', default='2017-12')
    specialty = request.form.get('specialty')
    
    if start_my == '':
        start_my = '2010-01'
    if end_my == '':
        end_my = '2017-12'


    data_req = request.form.get('data_query', default='n/a')
    
    logging.info('Received request to show data %s from specialty %s from time frame %s to %s' % (data_req, specialty, start_my, end_my))

    data_response = None
    if data_req == 'cuis':
        data_response = cui_counts(specialty, start_my, end_my)
    elif data_req == 'triage':
        data_response = triage_counts(specialty, start_my, end_my)
    else:
        # no request, show cuis by default
        data_response = cui_counts(specialty, start_my, end_my)
    
    return render_template('tracker.html', data=data_response, specialties=specialties, specialty=specialty, data_req=data_req)

def triage_counts(specialty, start_my, end_my):
    logging.info("Collecting triage counts into good format")
    start_year,start_month_in = [int(x) for x in start_my.split('-')]
    end_year, end_month_in = [int(x) for x in end_my.split('-')]

    cur = get_triage_db().cursor()
    cur.execute('select distinct status from triage')
    statuses = [row[0] for row in cur]
    if "Unknown" in statuses:
        statuses.remove("Unknown")
    
    cur.execute('select count from triage where specialty=? and date(date) between date(?) and date(?)', (specialty, start_my, end_my))
    
    data = []
    for status in statuses:
        data.append({})
        data[-1]['id'] = status
        data[-1]['values'] = []
        
        for year in range(start_year, end_year+1):
            if year > start_year:
                start_month = 1
            else:
                start_month = start_month_in
            if year < end_year:
                end_month = 12
            else:
                end_month = end_month_in
                
            for month in range(start_month, end_month):
                ym = '%4d-%02d' % (year, month)
                cur.execute('select count from triage where status=? and specialty=? and date=?', (status,specialty,ym))
                try:
                    count = cur.fetchone()[0]
                except:
                    count = 0
                data[-1]['values'].append({'date':ym, 'count':count})

    return {'chart_data':data}

def cui_counts(specialty, start_my, end_my):
    logging.info("Collecting cui counts into usable format")
    start_year,start_month_in = [int(x) for x in start_my.split('-')]
    end_year, end_month_in = [int(x) for x in end_my.split('-')]
    
    num_cuis = int(request.form.get('top', default='5'))
    
    cur = get_db().cursor()

    # First get top 5 counts across all time
    # currently hard-coded at 5 by html
    # Now get the count for each of these cuis for each month
    cur.execute('select cui from (select cui,count(cui) as frequency from cuis group by cui order by -count(cui) limit ?)', (num_cuis,) )
    cuis = []
    for row in cur:
        cuis.append(row[0])
                    
    rows = []
    for cui in cuis:
        rows.append({})
        rows[-1]['id'] = cui
        rows[-1]['values'] = []
        
        for year in range(start_year, end_year+1):
            if year > start_year:
                start_month = 1
            else:
                start_month = start_month_in
            if year < end_year:
                end_month = 12
            else:
                end_month = end_month_in
            
            for month in range(start_month, end_month):
                ym = '%4d-%02d' % (year, month)
                cur.execute('select count from cui_counts where cui=? and date=?', (cui,ym))
                cui_count = cur.fetchone()[0]
                
                rows[-1]['values'].append({'date':ym, 'count':cui_count})
        
    
    data = {'chart_data':rows}
    return data

@app.route("/cuis2")
def cui_counts2():
    start_year = int(request.args.get('start_year', default='2010'))
    start_month_in = int(request.args.get('start_month', default='1'))
    end_year = int(request.args.get('end_year', default='2017'))
    end_month_in = int(request.args.get('end_month', default='12'))
    num_cuis = int(request.args.get('top', default='5'))
    
    cur = get_db().cursor()
    # First get top 5 counts across all time
    # currently hard-coded at 5 by html
    cur.execute('select cui from (select cui,count(cui) as frequency from cuis group by cui order by -count(cui) limit ?)', (num_cuis,) )
    cuis = []
    for row in cur:
        cuis.append(row[0])
    
    
    # Now get the count for each of these cuis for each month
    rows = [ [] for cui in cuis ]
    dates = []
    
    for year in range(start_year, end_year+1):
        if year > start_year:
            start_month = 1
        else:
            start_month = start_month_in
        if year < end_year:
            end_month = 12
        else:
            end_month = end_month_in

        for month in range(start_month, end_month):
            ym = '%4d-%02d' % (year, month)
            dates.append(ym)
            #rows.append({'Date': ym, 'cuis': []})
            for cui_ind,cui in enumerate(cuis):
                # get the count for this cui in this month:
                # cur.execute("select count(cui) from cuis INNER JOIN econsults on cuis.row_id = econsults.row_id where cuis.cui=? and date(econsults.date) between date('%s-01') and date('%s-31')" % (ym, ym), (cui,))
                cur.execute('select count from cui_counts where cui=? and date=?', (cui,ym))
                cui_count = cur.fetchone()[0]
                # data[ym][cui] = cur.fetchone()[0]
                # rows[-1]['CUI%d' %(cui_ind+1)] = cur.fetchone()[0]
                # rows[-1]['CUI%dLabel' % (cui_ind+1)] = cui
                #rows[-1]['cuis'].append({'cui':cui, 'count':cui_count})
                rows[cui_ind].append(cui_count)
                

    data = {'chart_data': {'dates': dates, 'values':rows}}
    return render_template('cuis.html', data=data)


        
if __name__ == "__main__":
    # conn = sqlite3.connect('../liver+gastro_2010-2017.sql')
    # cur = conn.cursor()
    app.run(debug=True)
    # close_db()
    # conn = sqlite3.connect(sys.argv[0])
    # cur = conn.cursor()