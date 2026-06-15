import os
import sqlite3
import pandas as pd

def append_to_history(df: pd.DataFrame, filename: str = "history_expenses.csv"):
    """
    Filtruje pozycje zaznaczone jako 'Uwzględnij' i dopisuje je
    do pliku CSV działającego jako lokalna baza danych.
    """
    # Wybieramy tylko zatwierdzone pozycje
    approved_df = df[df["Uwzględnij"] == True].copy()

    if approved_df.empty:
        return False

    # Usuwamy kolumnę techniczną z checkboxem przed zapisem
    approved_df = approved_df.drop(columns=["Uwzględnij"])

    # Dodajemy znacznik czasu zapisu
    approved_df["Data dodania"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    # Zapis (jeśli plik nie istnieje, tworzy go wraz z nagłówkiem)
    file_exists = os.path.isfile(filename)
    approved_df.to_csv(filename, mode='a', index=False, header=not file_exists, encoding='utf-8')
    return True


DB_PATH = "wydatki.db"


def init_database():
    """
    Tworzy plik bazy danych oraz tabelę 'paragony', jeśli jeszcze nie istnieją.
    Uruchamiane raz przy starcie aplikacji.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tworzymy strukturę tabeli SQL zgodną z naszym DataFrame
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS paragony
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       nazwa_pozycji
                       TEXT
                       NOT
                       NULL,
                       cena_pln
                       REAL
                       NOT
                       NULL,
                       kategoria
                       TEXT
                       NOT
                       NULL,
                       data_zapisu
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   ''')
    conn.commit()
    conn.close()


def save_to_sqlite(df: pd.DataFrame) -> bool:
    """
    Filtruje DataFrame (tylko zaznaczone 'Uwzględnij') i zapisuje wiersze do bazy SQLite.
    """
    # 1. Filtrujemy tylko te pozycje, które użytkownik chce uwzględnić
    approved_df = df[df["Uwzględnij"] == True].copy()

    if approved_df.empty:
        return False  # Brak danych do zapisu

    # 2. Czyścimy dane: usuwamy techniczną kolumnę z checkboxem Streamlita
    approved_df = approved_df.drop(columns=["Uwzględnij"])

    # 3. Zmieniamy nazwy kolumn na zgodne z tabelą SQL (bez polskich znaków i spacji)
    approved_df = approved_df.rename(columns={
        "Nazwa pozycji": "nazwa_pozycji",
        "Cena (PLN)": "cena_pln",
        "Kategoria": "kategoria"
    })

    # 4. Dodajemy aktualny timestamp dla każdego wpisu
    approved_df["data_zapisu"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    # 5. Nawiązanie połączenia i bezproblemowy zapis przez Pandas
    conn = sqlite3.connect(DB_PATH)

    # if_exists="append" oznacza, że dopisujemy nowe wiersze do istniejącej tabeli
    approved_df.to_sql("paragony", conn, if_exists="append", index=False)

    conn.close()
    return True


def get_all_expenses() -> pd.DataFrame:
    """
    Funkcja pomocnicza: pobiera całą historię wydatków z bazy.
    Przydatna, jeśli zechcesz zrobić nową zakładkę w aplikacji z historią.
    """
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM paragony ORDER BY data_zapisu DESC", conn)
    conn.close()
    return df


def get_category_summary() -> pd.DataFrame:
    """
    Zwraca zagregowane statystyki dotyczące wydatków w poszczególnych kategoriach.
    """
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    query = """
            SELECT kategoria as 'Kategoria', COUNT(id) as 'Liczba pozycji', SUM(cena_pln) as 'Suma (PLN)', AVG(cena_pln) as 'Średnia cena pozycji (PLN)', MAX(cena_pln) as 'Najdroższy zakup (PLN)'
            FROM paragony
            GROUP BY kategoria
            ORDER BY [Suma (PLN)] DESC \
            """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_monthly_trend() -> pd.DataFrame:
    """
    Zwraca sumę wydatków pogrupowaną po miesiącach i kategoriach do wykresów liniowych/słupkowych.
    """
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    # Wyciągamy rok i miesiąc z daty zapisu
    query = """
            SELECT strftime('%Y-%m', data_zapisu) as 'Miesiąc', kategoria as 'Kategoria', SUM(cena_pln) as 'Suma'
            FROM paragony
            GROUP BY strftime('%Y-%m', data_zapisu), kategoria
            ORDER BY 'Miesiąc' ASC \
            """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df