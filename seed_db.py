import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "wydatki.db"

# 1. Zaktualizowana, oficjalna lista kategorii systemowych
CATEGORIES = [
    "Żywność",
    "Transport & Paliwo",
    "Mieszkanie & Rachunki",
    "Elektronika & Software",
    "Rozrywka & Kultura",
    "Zdrowie & Uroda",
    "Inne"
]

# 2. Próbki produktów dostosowane strukturalnie do nowych kategorii
PRODUCT_SAMPLES = {
    "Żywność": ["Zakupy spożywcze", "Pieczywo i nabiał", "Supermarket", "Restauracja", "Kawa i lunch"],
    "Transport & Paliwo": ["Tankowanie Pb95", "Bilet miesięczny MPK", "Przejazd Uber", "Karta miejska",
                           "Opłata parkingowa Autopay"],
    "Mieszkanie & Rachunki": ["Czynsz i media", "Środki czystości", "Artykuły domowe Ikea", "Proszek do prania",
                              "Rachunek za prąd"],
    "Elektronika & Software": ["Kabel USB-C Baseus", "Abonament GitHub Copilot", "Słuchawki bezprzewodowe",
                               "Subskrypcja iCloud", "Pendrive 64GB"],
    "Rozrywka & Kultura": ["Bilety kino", "Książka - Czysty Kod", "Subskrypcja Netflix", "Wyjście pub ze znajomymi",
                           "Bilet na koncert"],
    "Zdrowie & Uroda": ["Apteka - suplementy", "Karnet na siłownię", "Wizyta u dentysty", "Krem ochronny",
                        "Krople do oczu"],
    "Inne": ["Prezent urodzinowy", "Opłata skarbowa", "Kurier DHL", "Prowizja bankowa"]
}


def generate_fake_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Inicjalizacja tabeli w przypadku jej braku
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

    # ZABEZPIECZENIE: Sprawdzenie obecności wpisów w bazie danych
    cursor.execute("SELECT COUNT(*) FROM paragony")
    count = cursor.fetchone()[0]

    if count > 30:
        print(
            f"Abort: Baza danych zawiera już {count} rekordów. Generowanie przerwane w celu ochrony przed duplikacją.")
        conn.close()
        return

    print("Generowanie rekordów historycznych...")

    # Zakres czasowy operacji: kwiecień i maj 2026 roku
    start_date = datetime(2026, 4, 1)
    end_date = datetime(2026, 5, 31)
    delta_days = (end_date - start_date).days

    # Generowanie paczki 60 transakcji testowych
    for _ in range(60):
        random_day = start_date + timedelta(days=random.randint(0, delta_days))
        random_time = random_day.replace(hour=random.randint(8, 20), minute=random.randint(0, 59))

        category = random.choice(CATEGORIES)
        product_name = random.choice(PRODUCT_SAMPLES[category])

        # Logika widełek cenowych przypisana do charakteru kategorii
        if category == "Elektronika & Software":
            price = round(random.uniform(40.0, 450.0), 2)
        elif category == "Mieszkanie & Rachunki":
            price = round(random.uniform(50.0, 600.0), 2)
        elif category == "Żywność":
            price = round(random.uniform(12.0, 190.0), 2)
        else:
            price = round(random.uniform(10.0, 130.0), 2)

        timestamp = random_time.strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            "INSERT INTO paragony (nazwa_pozycji, cena_pln, kategoria, data_zapisu) VALUES (?, ?, ?, ?)",
            (product_name, price, category, timestamp)
        )

    conn.commit()
    conn.close()
    print("Sukces: Pomyślnie zasilono bazę SQLite 60 ustrukturyzowanymi rekordami.")

if __name__ == "__main__":
    generate_fake_data()