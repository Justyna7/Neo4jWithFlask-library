# Flask backend server for library project using Neo4j database
### creating neo4j container on docker:
on Windows:
```
docker run --name project-library -p7474:7474 -p7687:7687 -d -v C:\\neo4j\data:/data -v C:\\neo4j\logs:/logs -v C:\\neo4j\import:/var/lib/neo4j/import -v C:\\neo4j\plugins:/plugins -e NEO4J_AUTH=neo4j/test1234 -e NEO4J_apoc_export_file_enabled=true -e NEO4J_apoc_import_file_enabled=true -e NEO4J_apoc_import_file_use__neo4j__config=true -e 'NEO4JLABS_PLUGINS=[\"apoc\"]' neo4j:latest
```

on Linux:
```
docker run --name project-library -p7474:7474 -p7687:7687 -d -v C:\\neo4j\data:/data -v C:\\neo4j\logs:/logs -v C:\\neo4j\import:/var/lib/neo4j/import -v C:\\neo4j\plugins:/plugins -e NEO4J_AUTH=neo4j/test1234 -e NEO4J_apoc_export_file_enabled=true -e NEO4J_apoc_import_file_enabled=true -e NEO4J_apoc_import_file_use__neo4j__config=true -e NEO4JLABS_PLUGINS=["apoc"] neo4j:latest
```

### entering data
This step may be ommited.
Copy data from `Books.cypher` file info neo4j browser at `http://localhost:7474/browser`

### starting server
1. Install requirements by `pip install -r requirements.txt` command.
2. Start server using `python app.py` command
