import os
import pandas as pd
from sqlalchemy import create_engine


def get_db_engine():
    """
    Pobiera adres URL bazy danych z sekretów i konfiguruje silnik
    z jawnym przekazaniem parametrów, aby uniknąć błędów autoryzacji poolera.
    """
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("❌ BŁĄD: Brak zmiennej SUPABASE_DB_URL w konfiguracji sekretów Streamlit!")

    # 1. Jeśli z pośpiechu adres ma standardowy prefix, ujednolicamy go pod pg8000
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+pg8000://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1)

    # 2. Dla bezpiecznego poolingu w Supabase V2 na porcie 6543 dodajemy parametry wykonawcze
    # Rezygnujemy ze zmiennych przygotowywanych (prepared statements), które wywalają pooler
    return create_engine(
        db_url,
        connect_args={
            "timeout": 30,
            "tcp_keepalive": True
        }
    )


def init_database():
    """
    W wersji chmurowej struktura bazy (tabela 'paragony') została zainicjalizowana
    ręcznie bezpośrednio w edytorze SQL panelu Supabase.
    Funkcja pozostaje pusta, aby zachować pełną kompatybilność z app.py.
    """
    pass


def save_to_sqlite(df: pd.DataFrame) -> bool:
    """
    Nazwa funkcji zostaje niezmieniona z wersji lokalnej (dzięki temu app.py działa bez modyfikacji).
    Wewnątrz logika przekierowuje i zapisuje zatwierdzony koszyk bezpośrednio w chmurze Supabase.
    """
    # Filtrujemy tylko pozycje oznaczone przez użytkownika jako aktywne
    approved_df = df[df["Uwzględnij"] == True].copy()
    if approved_df.empty:
        return False

    # Czyszczenie i mapowanie nazw kolumn pod strukturę bazy danych PostgreSQL
    approved_df = approved_df.drop(columns=["Uwzględnij"])
    approved_df = approved_df.rename(columns={
        "Nazwa pozycji": "nazwa_pozycji",
        "Cena (PLN)": "cena_pln",
        "Kategoria": "kategoria"
    })

    # Dodajemy sygnaturę czasową zapisu w formacie strefy czasowej UTC
    approved_df["data_zapisu"] = pd.Timestamp.now(tz="UTC")

    # Łączenie i natychmiastowy upload paczki danych do tabeli w chmurze
    engine = get_db_engine()
    approved_df.to_sql("paragony", engine, if_exists="append", index=False)
    return True


def get_all_expenses() -> pd.DataFrame:
    """
    Pobiera kompletny rejestr transakcji historycznych z chmury Supabase
    sortując wpisy od najnowszych.
    """
    try:
        engine = get_db_engine()
        query = "SELECT id, nazwa_pozycji, cena_pln, kategoria, data_zapisu FROM paragony ORDER BY data_zapisu DESC"
        df = pd.read_sql_query(query, engine)
        return df
    except Exception:
        # Bezpiecznik: w przypadku pustej tabeli lub braku sieci zwraca czysty szkielet danych
        return pd.DataFrame()


def get_category_summary() -> pd.DataFrame:
    """
    Wykonuje zaawansowaną agregację i kalkulację statystyk kosztowych
    bezpośrednio na silniku bazodanowym PostgreSQL.
    """
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
    """
    Analizuje strumień kosztów w czasie, grupując dane do formatu rok-miesiąc.
    Dostosowane do specyficznej dla PostgreSQL składni funkcji to_char().
    """
    try:
        engine = get_db_engine()
        query = """
                SELECT TO_CHAR(data_zapisu, 'YYYY-MM') as "Miesiąc", \
                       kategoria                       as "Kategoria", \
                       SUM(cena_pln)                   as "Suma"
                FROM paragony
                GROUP BY TO_CHAR(data_zapisu, 'YYYY-MM'), kategoria
                ORDER BY "Miesiąc" ASC \
                """
        return pd.read_sql_query(query, engine)
    except Exception:
        return pd.DataFrame()