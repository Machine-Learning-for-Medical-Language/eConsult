import os
from os import path
from os.path import join
import sys
import csv
import logging

years = [2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017]

def get_text_for_row(root_dir, row_id):
    for year in years:
        year_dir = join(root_dir, 'text', '%d' % (year))
        plain_fn = join(year_dir, '%d.0.txt' % (row_id))
        q_fn = join(year_dir, 'questions', '%d.0.txt' % (row_id))
        l2_fn = join(year_dir, '%02d' % (row_id % 100), '%d.0.txt' % (row_id))
                    
        text = None
        if path.exists(plain_fn):
            with open(plain_fn, 'rt') as fin:
                text = fin.read()
        elif path.exists(q_fn):
            with open(q_fn, 'rt') as fin:
                text = fin.read()
        elif path.exists(l2_fn):
            with open(l2_fn, 'rt') as fin:
                text = fin.read()
    
        if not text is None:
            break
            
    return text

class EconsultRow():
    def __init__(self, row_id, provider_id, provider_level, provider_clinic, specialty, creation_date, disposition, note_text, note_path, reply_text, reply_path, audit_trail, yob, pt_lang, pt_eth, pt_sex):
        self.row_id = row_id
        self.provider_id = provider_id
        self.provider_level = provider_level
        self.provider_clinic = provider_clinic
        self.specialist_dept = specialty
        self.creation_date = creation_date
        self.disposition = disposition
        self.note_text = note_text
        self.note_path = note_path
        self.reply_text = reply_text
        self.reply_path = reply_path
        self.audit_trail = audit_trail
        self.yob = yob
        self.pt_lang = pt_lang
        self.pt_eth = pt_eth
        self.pt_sex = pt_sex

class EconsultYear():
    ''' This class can be used to access different pieces of data related to
    eConsult data downloaded from SFDPH. Pass in the path on your local machine
    and the year you would like to access to get an object that can iterate over
    eConsult rows or get individual rows by unique ID.
    Arguments:
    root_dir : The string path to the folder on the shared drive containing the
                metadata/ and text/ sub-directories.
    year : The year of data you want to access
    '''

    def __init__(self, root_dir, year, specialty=None, skipText=False):

        self.year = int(year)
        if not self.year in years:
            raise FileNotFoundError('The year passed in: %d does not exist' % (self.year))

        self.csv_path = join( join(root_dir, 'metadata'), 'metadata-%d.csv' % (self.year))
        
        self.text_dir = join( join(root_dir, 'text'), '%d' % self.year)
        ## After 2013 we added separate sub-directories for questions and replies
        ## because the directories were getting too big
        ## 5/10/2020: RE-did the pre-processing to create question/reply dirs for each year.
        if self.year >= 2008:
            self.question_dir = join(self.text_dir, 'questions')
            self.reply_dir = join(self.text_dir, 'replies')
        else:
            self.question_dir = self.text_dir
            self.reply_dir = self.text_dir
        self.csv_file = open(self.csv_path, newline='')
        self.csvreader = csv.reader(self.csv_file, delimiter=',', quotechar='"')
        if not type(specialty) is list:
            specialty = [specialty]
        self.specialty = specialty
        self.skipText = skipText
        self.disposition_map = self.read_dispositions(join(root_dir, 'updated_dispositions'))
        
    def close(self):
        self.csv_file.close()

    def __iter__(self):
        return self
    
    def read_dispositions(self, csv_folder):
        id2status = {}
        fn = join(csv_folder, '%4d.csv' % self.year)
        with open(fn) as df:
            reader = csv.DictReader(df)
            for row in reader:
                try:
                    row_id = int(row[reader.fieldnames[0]])
                    status = row[reader.fieldnames[8]]
                    id2status[row_id] = status
                except:
                    logging.warn('Could not parse the row_id for a record in the file %s' % (fn))
                    
        return id2status
    
    def __next__(self):
        # for csv_row in self.csvreader:
        #try:
        while(True):
            csv_row = next(self.csvreader)
            # if caller provided a specialty, iterate until we see one that has that specialty
            if (not csv_row[0] == '') and (self.specialty[0] is None or csv_row[4] in self.specialty):
                break
        #except StopIteration:
        #    return StopIteration

        # some row ids were exported as floats
        row_id = int(csv_row[0].replace('.0', ''))
        row_label = csv_row[0]
        if self.year == 2008:
            # 2008 is the only year without a decimal in the row id of the
            # metadata
            row_label = row_label + ".0"
        
        # Go get the notes from the text subdirectories:
        note_text = ''
        reply_text = ''
        if not self.skipText:
            if False and self.year == 2008:
                rownum = row_label.split(".")[0]
                last2digits = int(rownum) % 100
                note_fn = join(self.question_dir, '%02d' % (last2digits), '%s.txt' % (row_label))
            else:
                note_fn = join(self.question_dir, '%s.txt' % (row_label))
            with open(note_fn, 'r') as note_file:
                note_text = '\n'.join(note_file.readlines())

            if False and self.year == 2008:
                reply_fn = join(self.reply_dir, 'replies', '%s-reply.txt' % (row_label))
            else:
                reply_fn = join(self.reply_dir, '%s-reply.txt' % (row_label))
                
            with open(reply_fn, 'r') as reply_file:
                reply_text = '\n'.join(reply_file.readlines())
        
        disposition = self.disposition_map.get(row_id, "Unknown")

        row = EconsultRow(row_id,
                            csv_row[1],
                            csv_row[2],
                            csv_row[3],
                            csv_row[4],
                            csv_row[5],
                            disposition,
                            note_text, note_fn,
                            reply_text, reply_fn,
                            csv_row[10],
                            csv_row[12],
                            csv_row[13],
                            csv_row[14],
                            csv_row[15])
        return row

