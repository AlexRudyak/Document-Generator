import sqlite3

conn = sqlite3.connect('app.db')
c = conn.cursor()

c.execute("SELECT id, document_number, unique_identifier, revision_number, classification, signature_path, content, created_date FROM document")
docs = c.fetchall()

c.execute("DROP TABLE document")

c.execute("""
CREATE TABLE document (
    id INTEGER NOT NULL, 
    document_number VARCHAR(50) NOT NULL, 
    unique_identifier VARCHAR(36) NOT NULL, 
    revision_number INTEGER NOT NULL, 
    classification VARCHAR(50), 
    signature_path VARCHAR(255), 
    content TEXT NOT NULL, 
    created_date DATETIME, 
    PRIMARY KEY (id)
)
""")

c.execute("CREATE INDEX ix_document_document_number ON document (document_number)")
c.execute("CREATE INDEX ix_document_unique_identifier ON document (unique_identifier)")

c.executemany("INSERT INTO document (id, document_number, unique_identifier, revision_number, classification, signature_path, content, created_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", docs)

conn.commit()
conn.close()
print("Migration completed!")
