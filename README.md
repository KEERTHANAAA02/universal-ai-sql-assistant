# Universal AI SQL Assistant

This project converts normal English questions into SQL queries using Ollama + Llama 3.2 and shows the result in Streamlit.

## What is upgraded?

Earlier, the app worked only with two fixed tables: `customers` and `orders`.

Now it can:

- Use the sample database
- Upload any CSV file and convert it into a SQL table
- Upload multiple CSV files
- Automatically read table names and column names
- Generate SQL based on the actual database schema
- Connect to real databases using SQLAlchemy connection URLs
- Block unsafe SQL like DELETE, DROP, INSERT, UPDATE
- Show the generated SQL and result table

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

## Viva one-line answer

This upgraded project is a universal AI SQL assistant that can read any uploaded CSV or connected database schema, convert English questions into SQL queries, execute only safe read-only queries, and display the answer in a Streamlit web app.
