from app.models import Template, Document, DocCounter
from app import db
import json

def test_template_model(app):
    with app.app_context():
        t = Template(name="Test", content=json.dumps([{"type": "header", "text": "H"}]))
        db.session.add(t)
        db.session.commit()
        assert Template.query.count() == 1

def test_doc_counter(app):
    with app.app_context():
        c = DocCounter(counter=1)
        db.session.add(c)
        db.session.commit()
        
        c = DocCounter.query.first()
        c.counter += 1
        db.session.commit()
        
        assert DocCounter.query.first().counter == 2
