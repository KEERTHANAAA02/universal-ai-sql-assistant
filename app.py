import re
import sqlite3
from typing import Dict, List, Tuple

import ollama
import pandas as pd
import streamlit as st

try:
    from sqlalchemy import create_engine, inspect, text
except Exception:  # SQLAlchemy is optional until real DB connection is used
    create_engine = None
    inspect = None
    text = None


st.set_page_config(page_title="Universal AI SQL Assistant", page_icon="🤖", layout="wide")
st.title("🤖 Universal AI SQL Assistant")
st.caption("Ask questions in English. The app reads your database structure automatically and generates SQL.")


# -----------------------------
# Safety helpers
# -----------------------------
def clean_sql(raw_sql: str) -> str:
    """Remove markdown/code fences and keep a single SELECT/WITH query."""
    sql = raw_sql.strip()
    sql = re.sub(r"^```(?:sql)?", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"```$", "", sql).strip()
    sql = sql.rstrip(";").strip()
    return sql


def is_safe_read_only_query(sql: str) -> bool:
    """Allow only read-only SELECT/WITH queries."""
    blocked = [
        "insert", "update", "delete", "drop", "alter", "create", "truncate",
        "replace", "merge", "attach", "detach", "pragma", "vacuum", "grant", "revoke"
    ]
    lowered = sql.lower().strip()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False
    return not any(re.search(rf"\b{word}\b", lowered) for word in blocked)


def safe_table_name(name: str) -> str:
    """Make uploaded CSV filename safe as a SQL table name."""
    name = re.sub(r"\W+", "_", name.lower()).strip("_")
    if not name:
        name = "uploaded_table"
    if name[0].isdigit():
        name = "table_" + name
    return name[:50]


# -----------------------------
# SQLite demo / CSV database
# -----------------------------
@st.cache_resource
def init_sample_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            region TEXT,
            email TEXT
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product TEXT,
            amount REAL,
            order_date TEXT
        );

        INSERT INTO customers VALUES
            (1,'Alice','North','alice@example.com'),
            (2,'Bob','South','bob@example.com'),
            (3,'Carol','East','carol@example.com'),
            (4,'David','West','david@example.com'),
            (5,'Eva','North','eva@example.com');

        INSERT INTO orders VALUES
            (1,1,'Laptop',1200,'2024-01-15'),
            (2,2,'Phone',800,'2024-02-20'),
            (3,1,'Tablet',450,'2024-03-10'),
            (4,3,'Laptop',1200,'2024-03-25'),
            (5,4,'Phone',750,'2024-04-05'),
            (6,5,'Monitor',600,'2024-05-01'),
            (7,2,'Laptop',1150,'2024-06-18'),
            (8,3,'Tablet',480,'2024-07-22'),
            (9,1,'Phone',820,'2024-08-30'),
            (10,5,'Monitor',590,'2024-09-14');
    """)
    conn.commit()
    return conn


def build_csv_database(uploaded_files) -> Tuple[sqlite3.Connection, Dict[str, pd.DataFrame]]:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    tables = {}

    for uploaded_file in uploaded_files:
        table_name = safe_table_name(uploaded_file.name.rsplit(".", 1)[0])
        df = pd.read_csv(uploaded_file)
        df.columns = [safe_table_name(col) for col in df.columns]
        df.to_sql(table_name, conn, index=False, if_exists="replace")
        tables[table_name] = df

    conn.commit()
    return conn, tables


def get_sqlite_schema(conn: sqlite3.Connection) -> str:
    schema_lines: List[str] = []
    tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        conn,
    )["name"].tolist()

    for table in tables:
        cols = pd.read_sql(f'PRAGMA table_info("{table}")', conn)
        col_text = ", ".join([f"{row['name']} {row['type'] or 'TEXT'}" for _, row in cols.iterrows()])
        schema_lines.append(f"- {table}({col_text})")

    return "\n".join(schema_lines)


def show_sqlite_preview(conn: sqlite3.Connection):
    tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        conn,
    )["name"].tolist()

    for table in tables:
        with st.expander(f"📄 {table} table preview"):
            st.dataframe(pd.read_sql(f'SELECT * FROM "{table}" LIMIT 20', conn), use_container_width=True)


# -----------------------------
# Optional real database support
# -----------------------------
def get_sqlalchemy_schema(engine) -> str:
    db_inspector = inspect(engine)
    schema_lines = []
    for table_name in db_inspector.get_table_names():
        columns = db_inspector.get_columns(table_name)
        col_text = ", ".join([f"{col['name']} {col['type']}" for col in columns])
        schema_lines.append(f"- {table_name}({col_text})")
    return "\n".join(schema_lines)


def run_sql(sql: str, mode: str, conn=None, engine=None) -> pd.DataFrame:
    if mode == "Real Database":
        with engine.connect() as connection:
            return pd.read_sql(text(sql), connection)
    return pd.read_sql(sql, conn)


# -----------------------------
# Sidebar database choice
# -----------------------------
st.sidebar.header("Database Source")
source = st.sidebar.radio(
    "Choose data source",
    ["Sample Database", "Upload CSV", "Real Database"],
)

conn = None
engine = None
schema = ""
can_ask = False

if source == "Sample Database":
    conn = init_sample_db()
    schema = get_sqlite_schema(conn)
    can_ask = True
    st.info("Using sample database with customers and orders tables.")
    show_sqlite_preview(conn)

elif source == "Upload CSV":
    uploaded_files = st.sidebar.file_uploader(
        "Upload one or more CSV files",
        type=["csv"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        conn, _ = build_csv_database(uploaded_files)
        schema = get_sqlite_schema(conn)
        can_ask = True
        st.success("CSV file(s) loaded successfully. Each CSV became a SQL table.")
        show_sqlite_preview(conn)
    else:
        st.warning("Upload at least one CSV file to start asking questions.")

else:
    st.warning("Use this only for read-only analysis. Do not connect admin/root accounts.")
    db_type = st.sidebar.selectbox("Database type", ["PostgreSQL", "MySQL", "SQLite File"])

    if db_type == "SQLite File":
        sqlite_path = st.sidebar.text_input("SQLite file path", placeholder="example: company.db")
        if sqlite_path and st.sidebar.button("Connect SQLite"):
            try:
                conn = sqlite3.connect(sqlite_path, check_same_thread=False)
                schema = get_sqlite_schema(conn)
                st.session_state["real_conn"] = conn
                st.session_state["real_schema"] = schema
                st.session_state["real_engine"] = None
                st.success("Connected to SQLite file.")
            except Exception as e:
                st.error(f"Connection failed: {e}")
    else:
        st.sidebar.caption("Example PostgreSQL: postgresql+psycopg2://user:password@localhost:5432/dbname")
        st.sidebar.caption("Example MySQL: mysql+pymysql://user:password@localhost:3306/dbname")
        connection_url = st.sidebar.text_input("SQLAlchemy connection URL", type="password")
        if connection_url and st.sidebar.button("Connect Database"):
            if create_engine is None:
                st.error("Install SQLAlchemy and the correct driver first. Check requirements.txt.")
            else:
                try:
                    engine = create_engine(connection_url)
                    schema = get_sqlalchemy_schema(engine)
                    st.session_state["real_engine"] = engine
                    st.session_state["real_schema"] = schema
                    st.session_state["real_conn"] = None
                    st.success("Connected successfully.")
                except Exception as e:
                    st.error(f"Connection failed: {e}")

    conn = st.session_state.get("real_conn")
    engine = st.session_state.get("real_engine")
    schema = st.session_state.get("real_schema", "")
    can_ask = bool(schema)

    if schema:
        with st.expander("📌 Auto-read database schema"):
            st.code(schema, language="text")


# -----------------------------
# Ask AI and run query
# -----------------------------
st.markdown("---")
st.subheader("Ask your database")

with st.expander("📌 Current schema used by AI", expanded=False):
    st.code(schema or "No schema loaded yet.", language="text")

question = st.text_input(
    "💬 Type your question in English",
    placeholder="Example: Show top 5 products by total sales",
)

model_name = st.sidebar.text_input("Ollama model", value="llama3.2")
limit_rows = st.sidebar.number_input("Default row limit", min_value=10, max_value=1000, value=100, step=10)

if st.button("🔍 Generate & Run SQL", type="primary", disabled=not can_ask):
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("AI is reading the schema and writing SQL..."):
            try:
                dialect = "SQLite" if source in ["Sample Database", "Upload CSV"] or conn is not None else "SQL"
                prompt = f"""
You are an expert SQL assistant.
Convert the user's English question into one safe read-only {dialect} query.

Database schema:
{schema}

Rules:
1. Return ONLY the SQL query.
2. Do not use markdown or explanations.
3. Use only the tables and columns shown in the schema.
4. Generate only SELECT or WITH queries.
5. Do not generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, or any write operation.
6. If the user asks for many rows and no limit is mentioned, add LIMIT {limit_rows}.

User question: {question}
"""

                response = ollama.chat(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                )
                sql_query = clean_sql(response["message"]["content"])

                st.subheader("📝 Generated SQL")
                st.code(sql_query, language="sql")

                if not is_safe_read_only_query(sql_query):
                    st.error("Blocked unsafe SQL. This app only runs SELECT/WITH queries.")
                else:
                    result_df = run_sql(sql_query, source, conn=conn, engine=engine)
                    st.subheader("📊 Result")
                    st.dataframe(result_df, use_container_width=True)
                    st.success(f"Query returned {len(result_df)} row(s).")

            except Exception as e:
                st.error(f"Error: {e}")
                st.info("Check if Ollama is running and the selected model is installed. Example: ollama run llama3.2")

st.markdown("---")
st.caption("Built with Streamlit + Ollama + SQLite/SQLAlchemy. Use read-only database users for real databases.")
