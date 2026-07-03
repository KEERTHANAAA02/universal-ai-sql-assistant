# Universal AI SQL Assistant

This project converts normal English questions into SQL queries using Ollama + Llama 3.2 and shows the result in Streamlit.

## Simple explanation

User asks in English:

> Show top 5 products by total sales

The AI reads the database schema, creates SQL, runs it, and shows the answer.

Flow:

```text
English question -> AI reads schema -> SQL query -> Database -> Result table
```

## How to run

Install dependencies:

```bash
pip install -r requirements.txt
```

Start Ollama and install model:

```bash
ollama run llama3.2
```

Run the app:

```bash
streamlit run app.py
```

## CSV mode

1. Select **Upload CSV** in the sidebar.
2. Upload one or more CSV files.
3. Each CSV becomes a table.
4. Ask questions about your data.

Example:

```text
Show average salary by department
```

## Real database mode

Select **Real Database** in the sidebar.

Examples:

PostgreSQL:

```text
postgresql+psycopg2://user:password@localhost:5432/dbname
```

MySQL:

```text
mysql+pymysql://user:password@localhost:3306/dbname
```

SQLite file:

```text
company.db
```

Important: Use a read-only database user for safety.

