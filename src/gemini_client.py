import os
import pandas as pd
from typing import List, Literal
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 1. Ładowanie zmiennych środowiskowych z pliku .env
load_dotenv()

# 2. Pobranie klucza i weryfikacja dostępności poświadczeń
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError(
        "❌ BŁĄD: Nie znaleziono zmiennej GEMINI_API_KEY w pliku .env! "
        "Upewnij się, że plik .env istnieje w głównym folderze projektu."
    )

# 3. Inicjalizacja klienta z jawnym przekazaniem klucza API
client = genai.Client(api_key=api_key)

# 4. Definicja sztywnego zbioru kategorii (zamknięty słownik systemowy)
SYSTEM_CATEGORIES = Literal[
    "Żywność",
    "Transport & Paliwo",
    "Mieszkanie & Rachunki",
    "Elektronika & Software",
    "Rozrywka & Kultura",
    "Zdrowie & Uroda",
    "Inne"
]

# Schemat pozycji paragonu dla walidacji danych wejściowych
class ReceiptItem(BaseModel):
    item_name: str = Field(description="Pełna nazwa produktu lub usługi na paragonie")
    price: float = Field(description="Cena brutto za daną pozycję w PLN")
    # Zastosowanie typu Literal wymusza na Gemini zwrot wyłącznie jednej z tych wartości
    category: SYSTEM_CATEGORIES = Field(
        description="Wybierz i przyporządkuj produkt wyłącznie do jednej z podanych kategorii."
    )

# Główny kontener danych strukturalnych zwracany przez interfejs API
class ReceiptStructure(BaseModel):
    items: List[ReceiptItem] = Field(description="Lista wszystkich wykrytych pozycji na paragonie")


def analyze_receipt_with_gemini(uploaded_file) -> ReceiptStructure:
    """
    Pobiera plik ze Streamlita, konwertuje go na bajty i przesyła do Gemini.
    Wymusza zwrot ustrukturyzowanego formatu JSON zgodnego ze schematem Pydantic.
    """
    # Pobranie surowych bajtów oraz typu MIME bezpośrednio z obiektu Streamlit
    image_bytes = uploaded_file.getvalue()
    mime_type = uploaded_file.type

    # Przygotowanie komponentu multimedialnego dla modelu
    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type,
    )

    # Konstrukcja jednoznacznego promptu wykonawczego
    prompt = (
        "Dokonaj szczegółowej analizy dołączonego paragonu. Wyodrębnij z niego każdą pojedynczą pozycję, "
        "odczytaj jej cenę i sklasyfikuj do odpowiedniej kategorii na podstawie dostarczonego schematu danych. "
        "Bądź precyzyjny, nie pomijaj żadnego produktu i nie modyfikuj wartości liczbowych."
    )

    # Zapytanie do modelu przy użyciu stabilnego silnika serii 2.5 (pakiet darmowy AI Studio)
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[image_part, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ReceiptStructure,
            temperature=0.1,  # Niska temperatura minimalizuje ryzyko halucynacji cenowych
        ),
    )

    # Walidacja tekstowego formatu JSON bezpośrednio do obiektów Pydantic i zwrot danych
    return ReceiptStructure.model_validate_json(response.text)


def generate_financial_insights(expenses_df: pd.DataFrame, user_context: str = "") -> str:
    """
    Generuje zaawansowany raport finansowy. Dane historyczne z bazy stanowią
    główny fundament analizy, a opcjonalny kontekst użytkownika służy jako
    dodatkowy filtr i uzupełnienie dla doradcy AI.
    """
    import pandas as pd  # Bezpieczny import lokalny dla Streamlit Cloud

    if expenses_df.empty:
        return "Brak danych w bazie, aby przeprowadzić analizę AI. Dodaj najpierw paragony!"

    # Kopia danych, aby nie mutować stanu aplikacji
    df_copy = expenses_df.copy()

    # 1. Przygotowanie agregatów liczbowych (Twarde Dane)
    total_spent = df_copy['cena_pln'].sum()
    category_summary = df_copy.groupby('kategoria')['cena_pln'].sum().to_string()
    recent_transactions = df_copy.head(10)[['nazwa_pozycji', 'cena_pln', 'kategoria']].to_string(index=False)

    df_copy['data_zapisu'] = pd.to_datetime(df_copy['data_zapisu'])
    monthly_trend = df_copy.groupby(df_copy['data_zapisu'].dt.to_period('M'))['cena_pln'].sum().to_string()

    # 2. Obsługa opcjonalnego kontekstu (Dynamiczny dodatek)
    context_injection = "Brak dodatkowych uwag od użytkownika."
    if user_context.strip():
        context_injection = (
            f"Użytkownik przekazał następujące cele/plany krótko- lub długoterminowe:\n"
            f"\"\"\"\n{user_context.strip()}\n\"\"\""
        )

    # 3. Konstrukcja zbalansowanego promptu systemowego
    prompt = f"""
    Jesteś elitarnym, niezależnym doradcą finansowym i mistrzem analizy danych (Data Science). 
    Twoim nadrzędnym zadaniem jest przeprowadzenie całościowej i obiektywnej analizy finansów użytkownika na podstawie jego REALNYCH twardych danych historycznych.

    =========================================
    1. FUNDAMENT ANALITYCZNY (TWARDE DANE)
    =========================================
    - Całkowity skumulowany koszt w systemie: {total_spent:.2f} PLN

    - Globalny podział wydatków na kategorie:
    {category_summary}

    - Historyczny trend wydatków (miesiąc po miesiącu):
    {monthly_trend}

    - Ostatnie operacje (kontekst bieżący):
    {recent_transactions}

    =========================================
    2. FILTR KONTEKSTOWY (DODATEK UŻYTKOWNIKA)
    =========================================
    {context_injection}

    =========================================
    STRUKTURA WYKONAWCZA RAPORTU (ZADANIA DLA AI)
    =========================================
    Wygeneruj zwięzły, konkretny raport budżetowy. Zastosuj poniższą strukturę:

    1. 📊 GLOBALNY PRZEGLĄD STRUKTURY KOSZTÓW: Na podstawie danych liczbowych wskaż, które kategorie realnie pożerają największą część kapitału. Oceń stabilność trendu miesięcznego.
    2. 🔍 DETEKCJA ANOMALII: Wskaż nietypowe skoki wydatków lub obciążenia (np. ubezpieczenia, serwisy, duże zakupy jednorazowe), które zaburzyły płynność finansową.
    3. 🧠 ODNIESIENIE DO PLANÓW UŻYTKOWNIKA (JEŚLI DOTYCZY): Przeanalizuj "Dodatek użytkownika" przez pryzmat jego "Fundamentu analitycznego". Odpowiedz na pytanie: Czy na podstawie wzorców jego wydatków, cele takie jak wakacje, oszczędności czy limity zarobkowe są realne do osiągnięcia? Co musi zmienić w obecnej strukturze kosztów, aby zrealizować te plany?
    4. 🎯 3 STRATEGICZNE REKOMENDACJE: Podaj dokładnie trzy, bezwzględnie konkretne i mierzalne akcje naprawcze dążące do optymalizacji budżetu.

    Formatuj raport przy użyciu nowoczesnego Markdown, emojek, pogrubień istotnych kwot i przejrzystych punktów. Unikaj ogólnikowych frazesów – operuj na liczbach podanych w fundamencie.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"❌ Nie udało się wygenerować analizy AI. Błąd: {str(e)}"