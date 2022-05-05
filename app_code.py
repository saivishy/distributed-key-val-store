class Person(db.Model):
    id = db.Column(db.Integer, primary_key= True)
    name = db.Column(db.String(200), nullable = False)
    hash = db.Column(db.Integer, nullable = False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return '<Record %r' % self.id

db.create_all()

## index route
@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        record_name = request.form['name']
        record_hash = request.form['hash']
        lead = os.environ.get('LEADER')
        if  lead == '1':
            files= {"name": (None,record_name) , "hash": (None,record_hash)}
            url1 = 'http://Node2:5000/'
            log1 = requests.post(url1,  files =files)
            url2 = 'http://Node3:5000/'
            log2 = requests.post(url2, files =files)
        else:
            print('NOT LEADER-------------------')
            print(os.environ.get('LEADER'))
        new_record = Person(name=record_name,hash=record_hash) 
        try:
            db.session.add(new_record)            
            db.session.commit()
            return redirect('/')
        except:
            return 'There was an issue adding the record'
    else:
        records = Person.query.order_by(Person.date_created).all()
        return render_template('index.html', records = records)

@app.route('/delete/<int:id>')
def delete(id):
    record_to_delete = Person.query.get_or_404(id)

    lead = os.environ.get('LEADER')
    if  lead == '1': 
        for node in range(2,4):
            url = f"http://Node{node}:5000/delete/{id}"
            log = requests.get(url)
            print(f"SENT to delete GET to Node{node}")
            print(log)
    else:
        print('NOT LEADER-------------------')
        print(os.environ.get('LEADER'))

    try:
        db.session.delete(record_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return 'There was an issue deleting that record'

@app.route('/update/<int:id>', methods= ['GET','POST'])
def update(id):
    record = Person.query.get_or_404(id)

    lead = os.environ.get('LEADER')
    if  lead == '1': 
        if request.method == 'POST':
            record.name = request.form['name']
            record_name = request.form['name']
            for node in range(2,4):
                url = f"http://Node{node}:5000//update/{id}"
                get_log = requests.get(url)
                print(f"SENT to update GET to Node{node}")
                print(get_log)
                
                files= {"name": (None,record_name)}
                post_log = requests.post(url,  files =files)
                print(f"SENT to update POST to Node{node}")
                print(post_log)
            
            try:
                db.session.commit()
                return redirect('/')
            except:
                return 'There was an issue updating the record'
        else:
            return render_template('update.html', record = record )
            
            
    else:
        print('NOT LEADER-------------------')
        print(os.environ.get('LEADER'))
    
    
    
        if request.method == 'POST':
            record.name = request.form['name']
            
            try:
                db.session.commit()
                return redirect('/')
            except:
                return 'There was an issue updating the record'
        else:
            return render_template('update.html', record = record )

