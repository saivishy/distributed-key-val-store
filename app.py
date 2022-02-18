from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app =  Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'

db = SQLAlchemy(app)

class Person(db.Model):
    id = db.Column(db.Integer, primary_key= True)
    name = db.Column(db.String(200), nullable = False)
    hash = db.Column(db.Integer, nullable = False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return '<Record %r' % self.id

## index route
@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        record_name = request.form['name']
        record_hash = request.form['hash']
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

    try:
        db.session.delete(record_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return 'There was an issue deleting that record'

@app.route('/update/<int:id>', methods= ['GET','POST'])
def update(id):
    record = Person.query.get_or_404(id)
    if request.method == 'POST':
        record.name = request.form['name']
        
        try:
            db.session.commit()
            return redirect('/')
        except:
            return 'There was an issue updating the record'
    else:
        return render_template('update.html', record = record )

# @app.route('/view/<int:id>')
# def view(id):
#     record_to_delete = Person.query.get_or_404(id)

#     try:
#         db.session.query(record_to_delete)
#         db.session.commit()
#         return redirect('/')
#     except:
#         return 'There was an issue deleting that record'

if __name__ == "__main__":
    app.run(debug=True, host ='0.0.0.0', port=5000)