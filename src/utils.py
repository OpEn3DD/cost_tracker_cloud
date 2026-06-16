import os
import pandas as pd
from sqlalchemy import create_engine


def get_db_engine():
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("Brak zmiennej SUPABASE_DB_URL w Secrets!")

    # Upewniamy się, że dialekt to dokładnie postgresql:// (czyli psycopg2)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    return create_engine(db_url)


def init_database():
    pass


def save_to_sqlite(df: pd.DataFrame) -> bool:
    approved_df = df[df["Uwzględnij"] == True].copy()
    if approved_df.empty:
        return False

    approved_df = approved_df.drop(columns=["Uwzględnij"])
    approved_df = approved_df.rename(columns={
        "Nazwa pozycji": "nazwa_pozycji",
        "Cena (PLN)": "cena_pln",
        "Kategoria": "kategoria"
    })

    approved_df["data_zapisu"] = pd.Timestamp.now(tz="UTC")

    engine = get_db_engine()
    approved_df.to_sql("paragony", engine, if_exists="append", index=False)
    return True


def get_all_expenses() -> pd.DataFrame:
    try:
        engine = get_db_engine()
        df = pd.read_sql_query("SELECT * FROM paragony ORDER BY data_zapisu DESC", engine)
        return df
    except Exception:
        return pd.DataFrame()


def get_category_summary() -> pd.DataFrame:
    try:
        engine = get_db_engine()
        query = 'SELECT kategoria as "Kategoria", SUM(cena_pln) as "Suma (PLN)" FROM paragony GROUP BY kategoria'
        return pd.read_sql_query(query, engine)
    except Exception:
        return pd.DataFrame()


def get_monthly_trend() -> pd.DataFrame:
    try:
        engine = get_db_engine()
        query = "SELECT TO_CHAR(data_zapisu, 'YYYY-MM') as \"Miesiąc\", kategoria as \"Kategoria\", SUM(cena_pln) as \"Suma\" FROM paragony GROUP BY TO_CHAR(data_zapisu, 'YYYY-MM'), kategoria"
        return pd.read_sql_query(query, engine)
    except Exception:
        return pd.DataFrame()