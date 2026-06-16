import streamlit as st
import pandas as pd
import plotly.express as px
from src.gemini_client import analyze_receipt_with_gemini, generate_financial_insights
from src.utils import init_database, save_to_sqlite, get_all_expenses, get_category_summary, get_monthly_trend

# Konfiguracja systemowa aplikacji
st.set_page_config(
    page_title="Cost Tracker",
    layout="centered",  # Natywne wyśrodkowanie i zwężenie widoku przez Streamlit
    initial_sidebar_state="collapsed"
)

# Inicjalizacja struktury bazodanowej
init_database()

# Nagłówek główny
st.title("System Analizy Wydatków i Struktur Kosztów")
st.caption("Aplikacja do automatycznej ekstrakcji danych fiskalnych i kategoryzacji budżetowej.")

# Rejestr stałych kategorii systemowych
CATEGORIES = [
    "Żywność",
    "Transport & Paliwo",
    "Mieszkanie & Rachunki",
    "Elektronika & Software",
    "Rozrywka & Kultura",
    "Zdrowie & Uroda",
    "Inne"
]

# Zarządzanie stanem sesji dla bufora danych bieżącego paragonu
if 'df_receipt' not in st.session_state:
    st.session_state.df_receipt = None

# --- KORPUS GŁÓWNY: Definicja Zakładek ---
tab_monthly, tab_comparison, tab_add_receipt, tab_history,tab_ai = st.tabs([
    "Przegląd miesięczny",
    "Porównanie okresów",
    "Dodaj paragon",
    "Rejestr transakcji",
    "Analiza AI"
])

# Pobranie danych bazowych do analiz globalnych
expenses_base = get_all_expenses()
if not expenses_base.empty:
    expenses_base['Miesiąc'] = pd.to_datetime(expenses_base['data_zapisu']).dt.to_period('M').astype(str)

# ==========================================
# ZAKŁADKA 1: PRZEGLĄD WYBRANEGO MIESIĄCA
# ==========================================
with tab_monthly:
    if not expenses_base.empty:
        available_months = sorted(expenses_base['Miesiąc'].unique(), reverse=True)
        selected_month = st.selectbox("Wybierz okres rozliczeniowy do analizy:", available_months,
                                      key="month_select_t1")

        month_df = expenses_base[expenses_base['Miesiąc'] == selected_month]
        st.markdown(f"### Podsumowanie kosztów dla okresu: {selected_month}")

        m_total = month_df['cena_pln'].sum()
        m_count = month_df['id'].count()

        col_m_kpi1, col_m_kpi2 = st.columns(2)
        col_m_kpi1.metric(label="Łączne wydatki w miesiącu", value=f"{m_total:.2f} PLN")
        col_m_kpi2.metric(label="Liczba zakupionych pozycji", value=f"{m_count} szt.")

        st.write("")
        st.markdown("#### Alokacja procentowa kapitału")
        m_pie_df = month_df.groupby('kategoria')['cena_pln'].sum().reset_index()
        fig_m_pie = px.pie(m_pie_df, values='cena_pln', names='kategoria', hole=0.5,
                           color_discrete_sequence=px.colors.qualitative.Plotly)
        fig_m_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_m_pie, use_container_width=True)

        st.markdown("#### Podział globalny na kategorie")
        m_summary = month_df.groupby('kategoria')['cena_pln'].sum().reset_index().rename(
            columns={'kategoria': 'Kategoria', 'cena_pln': 'Suma (PLN)'}
        )
        st.dataframe(m_summary, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Szczegółowy rejestr pozycji dla wybranej kategorii")
        active_categories_in_month = sorted(month_df['kategoria'].unique())
        selected_cat = st.selectbox("Wybierz kategorię do dekompozycji wydatków:", active_categories_in_month,
                                    key="monthly_cat_selector")

        filtered_cat_df = month_df[month_df['kategoria'] == selected_cat]
        if not filtered_cat_df.empty:
            display_cat_df = filtered_cat_df.rename(
                columns={"nazwa_pozycji": "Nazwa towaru / usługi", "cena_pln": "Cena brutto (PLN)",
                         "data_zapisu": "Data rejestracji"})
            cat_total = filtered_cat_df['cena_pln'].sum()
            st.caption(
                f"Łączny koszt pozycji w kategorii **{selected_cat}** w okresie {selected_month} wynosi: **{cat_total:.2f} PLN**")
            st.dataframe(display_cat_df[["Nazwa towaru / usługi", "Cena brutto (PLN)", "Data rejestracji"]],
                         column_config={"Cena brutto (PLN)": st.column_config.NumberColumn(format="%.2f zł")},
                         use_container_width=True, hide_index=True)
    else:
        st.info(
            "Baza danych nie zawiera jeszcze żadnych rekordów. Przejdź do zakładki 'Dodaj paragon', aby wprowadzić dane.")

# ==========================================
# ZAKŁADKA 2: PORÓWNANIE OKRESÓW
# ==========================================
with tab_comparison:
    if not expenses_base.empty:
        unique_months = sorted(expenses_base['Miesiąc'].unique())

        if len(unique_months) >= 2:
            st.markdown("### Analiza porównawcza strumieni kosztów")
            c_col1, c_col2 = st.columns(2)
            with c_col1:
                month_a = st.selectbox("Miesiąc bazowy (A):", unique_months, index=0, key="month_a_select")
            with c_col2:
                month_b = st.selectbox("Miesiąc porównywany (B):", unique_months, index=min(1, len(unique_months) - 1),
                                       key="month_b_select")

            df_a = expenses_base[expenses_base['Miesiąc'] == month_a]
            df_b = expenses_base[expenses_base['Miesiąc'] == month_b]

            sum_a = df_a['cena_pln'].sum()
            sum_b = df_b['cena_pln'].sum()
            diff = sum_b - sum_a
            percent_diff = (diff / sum_a) * 100 if sum_a > 0 else 0

            kpi_c1, kpi_c2, kpi_c3 = st.columns(3)
            kpi_c1.metric(label=f"Suma okresu A ({month_a})", value=f"{sum_a:.2f} PLN")
            kpi_c2.metric(label=f"Suma okresu B ({month_b})", value=f"{sum_b:.2f} PLN")
            kpi_c3.metric(label="Różnica nominalna", value=f"{diff:.2f} PLN", delta=f"{percent_diff:.1f}%",
                          delta_color="inverse")

            st.divider()

            comp_df = expenses_base[expenses_base['Miesiąc'].isin([month_a, month_b])]
            comp_grouped = comp_df.groupby(['Miesiąc', 'kategoria'])['cena_pln'].sum().reset_index()

            fig_comp = px.bar(
                comp_grouped, x='kategoria', y='cena_pln', color='Miesiąc', barmode='group',
                title="Porównanie bezpośrednie kategorii kosztowych",
                labels={'cena_pln': 'Wydatki (PLN)', 'kategoria': 'Kategoria'},
                color_discrete_sequence=px.colors.qualitative.Plotly
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info(
                "Do aktywacji modułu porównawczego wymagane są dane historyczne z co najmniej dwóch różnych miesięcy.")
    else:
        st.info("Baza danych nie zawiera rekordów.")

# ==========================================
# ZAKŁADKA 3: DODAJ WYDATEK (AI lub Ręcznie)
# ==========================================
with tab_add_receipt:
    st.markdown("### Metoda wprowadzenia danych")
    input_method = st.radio(
        "Wybierz w jaki sposób chcesz wprowadzić koszty:",
        ["Skaner dokumentu (AI)", "Manualny formularz (Ręcznie)"],
        horizontal=True,
        key="input_method_selector"
    )

    st.divider()

    # --- WARIANT A: AUTOMATYCZNA EKSTRAKCJA AI ---
    if input_method == "Skaner dokumentu (AI)":
        st.markdown("### Import Dokumentu")
        uploaded_file = st.file_uploader(
            "Wczytaj obraz dokumentu zakupu (Format: JPG, PNG)",
            type=["jpg", "jpeg", "png"],
            key="receipt_uploader_main"
        )

        if uploaded_file:
            st.image(uploaded_file, caption="Dokument źródłowy", use_container_width=True)

            if st.button("Uruchom proces ekstrakcji", type="primary", use_container_width=True):
                with st.spinner("Przetwarzanie obrazu przez AI..."):
                    try:
                        ai_result = analyze_receipt_with_gemini(uploaded_file)
                        items_list = [item.model_dump() for item in ai_result.items]
                        df = pd.DataFrame(items_list)

                        df = df.rename(columns={
                            "item_name": "Nazwa pozycji",
                            "price": "Cena (PLN)",
                            "category": "Kategoria"
                        })
                        df["Uwzględnij"] = True

                        st.session_state.df_receipt = df
                        st.rerun()
                    except Exception as e:
                        st.error(f"Błąd krytyczny modułu parsowania: {e}")

        st.divider()

        if st.session_state.df_receipt is not None:
            st.markdown("### Weryfikacja pozycji i zapis")
            edited_df = st.data_editor(
                st.session_state.df_receipt,
                num_rows="dynamic",
                column_config={
                    "Kategoria": st.column_config.SelectboxColumn("Kategoria systemowa", options=CATEGORIES,
                                                                  required=True),
                    "Cena (PLN)": st.column_config.NumberColumn(format="%.2f zł"),
                    "Uwzględnij": st.column_config.CheckboxColumn("Aktywny")
                },
                use_container_width=True,
                key="main_data_editor"
            )
            st.session_state.df_receipt = edited_df

            filtered_df = edited_df[edited_df["Uwzględnij"] == True]
            if not filtered_df.empty:
                total_cost = filtered_df["Cena (PLN)"].sum()
                st.metric(label="Wartość kalkulowana koszyka", value=f"{total_cost:.2f} PLN")

            st.write("")

            if st.button("Zatwierdź i zapisz sesję do bazy", type="primary", use_container_width=True):
                if save_to_sqlite(edited_df):
                    st.session_state.df_receipt = None
                    st.toast("Dane zostały zarchiwizowane.")
                    st.rerun()
                else:
                    st.warning("Brak aktywnych pozycji do zapisu.")
        else:
            st.caption("Wgraj plik powyżej, aby uruchomić edytor pozycji i kategoryzację AI.")

    # --- WARIANT B: FORMULARZ MANUALNY (NOWOŚĆ) ---
    else:
        st.markdown("### Nowy wydatek / rachunek")

        # Tworzymy formularz Streamlit, aby dane wysyłały się pakietem dopiero po kliknięciu
        with st.form("manual_expense_form", clear_on_submit=True):
            manual_name = st.text_input(
                "Nazwa towaru / usługi / rachunku:",
                placeholder="np. Czynsz za mieszkanie, Bilet miesięczny, Uber",
                help="Wpisz jednoznaczną nazwę dla identyfikacji wydatku."
            )

            manual_price = st.number_input(
                "Wartość transakcji (PLN):",
                min_value=0.01,
                max_value=100000.00,
                step=0.01,
                format="%.2f"
            )

            manual_category = st.selectbox(
                "Przypisz kategorię budżetową:",
                options=CATEGORIES,
                index=0
            )

            st.write("")
            submit_manual = st.form_submit_with_陰影 = st.form_submit_button(
                "Zarejestruj wydatek manualnie",
                type="primary",
                use_container_width=True
            )

            if submit_manual:
                if manual_name.strip() == "":
                    st.error("Pole 'Nazwa' nie może być puste!")
                else:
                    # Budujemy uproszczoną strukturę DataFrame identyczną z tą, którą generuje AI,
                    # dzięki czemu funkcja save_to_sqlite w utils.py przetworzy ją bez modyfikacji!
                    manual_data = {
                        "Nazwa pozycji": [manual_name.strip()],
                        "Cena (PLN)": [manual_price],
                        "Kategoria": [manual_category],
                        "Uwzględnij": [True]
                    }
                    df_manual = pd.DataFrame(manual_data)

                    with st.spinner("Zapisywanie w bazie chmurowej..."):
                        if save_to_sqlite(df_manual):
                            st.toast("Wydatek wprowadzony pomyślnie!")
                            st.rerun()
                        else:
                            st.error("Błąd zapisu strukturalnego do bazy danych.")

# ==========================================
# ZAKŁADKA 4: REJESTR TRANSAKCJI
# ==========================================
with tab_history:
    expenses_h = get_all_expenses()
    if not expenses_h.empty:
        global_total = expenses_h['cena_pln'].sum()
        st.metric(label="SKUMULOWANE CAŁKOWITE KOSZTY SYSTEMOWE", value=f"{global_total:.2f} PLN")
        st.divider()

        st.markdown("### Rejestr wszystkich rekordów")
        display_history = expenses_h.rename(columns={
            "id": "ID indeksu", "nazwa_pozycji": "Nazwa towaru/usługi",
            "cena_pln": "Cena brutto (PLN)", "kategoria": "Kategoria", "data_zapisu": "Sygnatura czasowa"
        })
        st.dataframe(
            display_history[
                ["ID indeksu", "Nazwa towaru/usługi", "Cena brutto (PLN)", "Kategoria", "Sygnatura czasowa"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Brak rekordów w archiwum systemowym.")

# ==========================================
# ZAKŁADKA 5: ANALIZA AI & DORADCA FINANSOWY
# ==========================================
with tab_ai:
    st.markdown("## 🧠 Inteligentny Doradca Finansowy GenSI")
    st.caption(
        "Moduł wykorzystuje generatywną sztuczną inteligencję Gemini do głębokiej analizy Twoich struktur kosztów."
    )
    st.divider()

    # Pobieramy dane z bazy
    expenses_all = get_all_expenses()

    if expenses_all.empty:
        st.info(
            "💡 Twój rejestr wydatków jest pusty. Dodaj lub zaimplementuj paragony, aby uruchomić analizę doradcy AI."
        )
    else:
        # Stan sesji, aby zapamiętać wygenerowany raport i nie odpytywać API przy każdym kliknięciu w UI
        if "ai_report" not in st.session_state:
            st.session_state.ai_report = None

        # PANEL KONTROLNY & INPUT UŻYTKOWNIKA
        st.markdown("### 📊 Generuj nowy raport kosztów")
        st.write("Model Gemini przeanalizuje trendy miesięczne, anomalie oraz sklasyfikuje ryzyka budżetowe.")

        # Nowe pole na dodatkowy kontekst od użytkownika
        user_input_context = st.text_area(
            "Dodatkowe informacje dla AI (opcjonalnie):",
            placeholder="np. Zarabiam 5000zł, w lipcu planuję wakacje, chcę zaoszczędzić na nowy rower.",
            help="Te informacje pomogą Gemini lepiej dopasować porady do Twojej obecnej sytuacji życiowej i planów."
        )

        # Przycisk uruchamiający analizę
        generate_button = st.button("🚀 Uruchom Analizę AI", use_container_width=True)

        if generate_button:
            with st.spinner("🧠 Sztuczna inteligencja analizuje Twoje finanse (szukanie anomalii i trendów)..."):
                # Wywołanie funkcji z gemini_client z uwzględnieniem dodatkowego kontekstu
                st.session_state.ai_report = generate_financial_insights(expenses_all, user_input_context)
                st.toast("Analiza AI wygenerowana pomyślnie!", icon="✅")
                st.rerun()  # Odświeżamy aplikację, aby od razu renderować nowy raport

        # WYŚWIETLANIE WYNIKÓW
        if st.session_state.ai_report:
            st.divider()
            st.markdown("### 📝 Wynik analizy strukturalnej Gemini:")
            st.info(st.session_state.ai_report)

            # Możliwość pobrania raportu jako plik tekstowy
            st.download_button(
                label="📥 Pobierz raport AI (.txt)",
                data=st.session_state.ai_report,
                file_name="raport_budzetowy_ai.txt",
                mime="text/plain",
                use_container_width=True
            )