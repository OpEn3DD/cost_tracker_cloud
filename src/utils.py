import os
import sqlite3
import pandas as pd
from sqlalchemy import create_engine


# Pobieranie adresu bazy z sekretów chmury Streamlit
def get_db_engine():
    # Streamlit Cloud przekaże nam pełny link w zmiennej środowiskowej
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("Brak zmiennej SUPABASE_DB_URL w konfiguracji sekretów!")

    # Podmieniamy prefix, ponieważ SQLAlchemy wymaga 'postgresql://' zamiast 'postgres://'
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    return create_engine(db_url)


def init_database():
    """W chmurze tabela jest tworzona ręcznie przez panel Supabase, funkcja pomocnicza."""
    pass


def save_to_sqlite(df: pd.DataFrame) -> bool:
    """
    Nazwa funkcji zostaje stara, aby nie zmieniać app.py!
    Wewnątrz logika wysyła dane prosto do chmury Supabase.
    """
    approved_df = df[df["Uwzględnij"] == True].copy()
    if approved_df.empty:
        return False

    approved_df = approved_df.drop(columns=["Uwzględnij"])
    approved_df = approved_df.rename(columns={
        "Nazwa pozycji": "nazwa_pozycji",
        "Cena (PLN)": "cena_pln",
        "Kategoria": "kategoria"
    })

    # Dodajemy timestamp w formacie UTC
    approved_df["data_zapisu"] = pd.Timestamp.now(tz="UTC")

    # Połączenie i natychmiastowy upload do chmury przez Pandas
    engine = get_db_engine()
    approved_df.to_sql("paragony", engine, if_exists="append", index=False)
    return True


def get_all_expenses() -> pd.DataFrame:
    """Pobiera dane na żywo z bazy PostgreSQL w chmurze."""
    try:
        engine = get_db_engine()
        df = pd.read_sql_query("SELECT * FROM paragony ORDER BY data_zapisu DESC", engine)
        return df
    except Exception:
        # Zwraca pusty DataFrame jeśli baza jest jeszcze pusta lub brak połączenia
        return pd.DataFrame()


def get_category_summary() -> pd.DataFrame:
    """Pobiera agregację kategorii na żywo z chmury."""
    try:
        engine = get_db_engine()
        query = """
                SELECT kategoria     as "Kategoria", \
                       COUNT(id)     as "Liczba pozycji", \
                       SUM(cena_pln) as "Suma (PLN)", \
                       AVG(cena_pln) as "Średnia cena pozycji (PLN)", \
                       MAX(cena_pln) as "Najdroższy zakup (PLN)"
                FROM paragony
                GROUP BY kategoria
                ORDER BY "Suma (PLN)" DESC \
                """
        return pd.read_sql_query(query, engine)
    except Exception:
        return pd.DataFrame()


def get_monthly_trend() -> pd.DataFrame:
    """Pobiera trendy miesięczne dostosowane do składni PostgreSQL."""
    try:
        engine = get_db_engine()
        query = """
                SELECT to_char(data_zapisu, 'YYYY-MM') as "Miesiąc", \
                       kategoria                       as "Kategoria", \
                       SUM(cena_pln)                   as "Suma"
                FROM paragony
                GROUP BY to_char(data_zapisu, 'YYYY-MM'), kategoria
                ORDER BY "Miesiąc" ASC \
                """
        return pd.read_sql_query(query, engine)
    except Exception:
        return pd.DataFrame()