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


def generate_financial_insights(expenses_df: pd.DataFrame) -> str:
    """
    Generuje spersonalizowane wnioski i porady finansowe na podstawie historii wydatków.
    """
    if expenses_df.empty:
        return "Brak danych w bazie, aby przeprowadzić analizę AI. Dodaj najpierw paragony!"

    # 1. Przygotowanie zagregowanych metryk tekstowych dla LLM
    total_spent = expenses_df['cena_pln'].sum()

    # Podsumowanie według kategorii
    category_summary = expenses_df.groupby('kategoria')['cena_pln'].sum().to_string()

    # Wyciągamy 10 ostatnich transakcji dla złapania kontekstu ostatnich działań
    recent_transactions = expenses_df.head(10)[['nazwa_pozycji', 'cena_pln', 'kategoria']].to_string(index=False)

    # Kontekst czasowy
    expenses_df['data_zapisu'] = pd.to_datetime(expenses_df['data_zapisu'])
    monthly_trend = expenses_df.groupby(expenses_df['data_zapisu'].dt.to_period('M'))['cena_pln'].sum().to_string()

    # 2. Budowa promptu dla Doradcy AI
    prompt = f"""
    Jesteś elitarnym, osobistym doradcą finansowym oraz analitykiem danych. Twoim zadaniem jest przeanalizowanie poniższych danych budżetowych użytkownika i dostarczenie mu potężnych, konkretnych i krytycznych wniosków (AI Insights).

    Oto podsumowanie finansowe użytkownika:
    - Całkowita suma wydatków w systemie: {total_spent:.2f} PLN

    - Podział wydatków na kategorie (Suma w PLN):
    {category_summary}

    - Trend wydatków w ujęciu miesięcznym:
    {monthly_trend}

    - Ostatnie 10 transakcji:
    {recent_transactions}

    Sformułuj swój raport w sposób profesjonalny, bezpośredni i konkretny. Unikaj ogólników typu "warto oszczędzać". Skup się na:
    1. **Wychwytywaniu anomalii i trendów:** (np. która kategoria dominuje, czy widać skoki w ujęciu miesięcznym, czy zdarzenia losowe mocno nadszarpnęły budżet).
    2. **Konkretnych rekomendacjach:** Gdzie realnie użytkownik może szukać optymalizacji kosztów na podstawie jego danych.
    3. **Prognozie/Ostrzeżeniu:** Krótkie podsumowanie, na co powinien uważać w najbliższym miesiącu.

    Formatuj odpowiedź używając czytelnych punktów Markdown, pogrubień i emotikon, aby raport wyglądał nowocześnie i przejrzyście w interfejsie Streamlit.
    """

    try:
        # Wywołanie modelu tekstowego
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"❌ Nie udało się wygenerować analizy AI. Błąd: {str(e)}"