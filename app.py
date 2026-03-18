import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ── 1. הגדרות דף ועיצוב (RTL ופלטת צבעים) ──
st.set_page_config(page_title="AI FinOps Dashboard", layout="wide", page_icon="📊")

# פלטת 4 צבעים מרכזיים לויזואליזציות
COLORS = ['#3366CC', '#109618', '#FF9900', '#DC3912'] # כחול (כללי), ירוק (יעילות), כתום (אזהרה), אדום (חריגה)

st.markdown("""
<style>
    .stApp { direction: rtl; }
    p, div, input, label, h1, h2, h3, h4, h5, h6, span { text-align: right !important; }
    [data-testid="stHorizontalBlock"] { flex-direction: row-reverse; }
    [data-testid="stMetricValue"], [data-testid="stMetricDelta"] { text-align: right; }
    .stDataFrame { direction: rtl; }
    /* עיצוב כותרות בולט יותר */
    h1 { color: #1f77b4; border-bottom: 2px solid #1f77b4; padding-bottom: 10px; }
    h2 { color: #ff7f0e; margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("📊 מערכת בקרה פיננסית - AI API")

# ── 2. מחירון מודלים דינמי (עלות למיליון טוקנים בדולרים) ──
PRICING_PER_1M = {
    "gpt-4o": {"input": 4.0, "output": 16.0},
    "o4-mini": {"input": 4.0, "output": 16.0},
    "gemini-2.5-flash-lite": {"input": 0.1, "output": 0.4},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.6},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.0}
}

# ── 3. טעינת נתונים חסינת שגיאות ──
@st.cache_data
def load_and_process_data(file_path):
    if not os.path.exists(file_path):
        return None
    
    df = pd.read_csv(file_path, sep=None, engine='python')
    df.columns = df.columns.str.strip().str.lower()
    
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        
    # חישוב עלויות דינמי לפי שורות
    def calculate_cost(row):
        model = row.get('model', '').lower()
        # אם המודל לא במחירון, נניח עלות 0 ונציג אזהרה
        prices = PRICING_PER_1M.get(model, {"input": 0.0, "output": 0.0}) 
        
        in_cost = (row.get('input_tokens', 0) / 1_000_000) * prices['input']
        out_cost = (row.get('output_tokens', 0) / 1_000_000) * prices['output']
        return in_cost + out_cost

    df['total_cost_usd'] = df.apply(calculate_cost, axis=1)
    df['total_tokens'] = df['input_tokens'] + df['output_tokens']
    
    return df

# נתיב לקובץ הנתונים המאוחד החדש
DATA_FILE = 'data/unified_usage_log.csv'
df = load_and_process_data(DATA_FILE)

if df is None:
    st.warning(f"ממתין לקובץ הנתונים. אנא ודא שהקובץ '{DATA_FILE}' קיים בתיקייה.")
else:
    # ── 4. סרגל צד (פילטרים) ──
    st.sidebar.header("🎯 סינון נתונים")
    date_range = st.sidebar.date_input("בחר טווח תאריכים", 
                                       [df['date'].min(), df['date'].max()])
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        # המרה ל-datetime כדי לסנן נכון
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        filtered_df = df.loc[mask]
    else:
        filtered_df = df

    # ── 5. בניית הלשוניות (Tabs) ──
    tab1, tab2, tab3, tab4 = st.tabs([
        "🌐 מבט על (Overview)", 
        "🧩 ניתוח לפי פיצ'ר", 
        "🤖 ניתוח לפי מודל", 
        "💡 כלכלה וחריגות (Unit Economics)"
    ])

    # --- לשונית 1: מבט על ---
    with tab1:
        st.header("סיכום ביצועים כולל")
        
        total_cost = filtered_df['total_cost_usd'].sum()
        total_calls = filtered_df['calls'].sum()
        total_tokens = filtered_df['total_tokens'].sum()
        avg_cost_per_call = total_cost / total_calls if total_calls > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("סך הוצאות ($)", f"${total_cost:,.2f}")
        col2.metric("קריאות API", f"{total_calls:,}")
        col3.metric("סך טוקנים שעובדו", f"{total_tokens:,}")
        col4.metric("עלות ממוצעת לקריאה", f"${avg_cost_per_call:,.4f}")
        
        st.markdown("---")
        
        # גרף הוצאות יומי
        daily_cost = filtered_df.groupby('date')['total_cost_usd'].sum().reset_index()
        fig_trend = px.area(daily_cost, x='date', y='total_cost_usd', 
                            title="מגמת הוצאות יומית (Burn Rate)",
                            labels={'date': 'תאריך', 'total_cost_usd': 'עלות ($)'},
                            color_discrete_sequence=[COLORS[0]])
        st.plotly_chart(fig_trend, use_container_width=True)

    # --- לשונית 2: ניתוח לפי פיצ'ר ---
# --- לשונית 2: ניתוח לפי פיצ'ר (משודרג) ---
    with tab2:
        st.header("🧩 ניתוח מעמיק לפי פיצ'ר")
        
        # 1. בחירת הפיצ'ר
        features_list = filtered_df['feature'].unique().tolist()
        selected_feature = st.selectbox("👇 בחר פיצ'ר לניתוח:", features_list)
        
        if selected_feature:
            st.markdown(f"### 📊 נתונים ממוקדים עבור: {selected_feature}")
            
            # סינון הנתונים רק לפי הפיצ'ר שנבחר
            feat_data = filtered_df[filtered_df['feature'] == selected_feature].copy()
            
            # 2. מדדים מרכזיים לפיצ'ר
            f_cost = feat_data['total_cost_usd'].sum()
            f_calls = feat_data['calls'].sum()
            f_tokens = feat_data['total_tokens'].sum()
            f_avg_cost = f_cost / f_calls if f_calls > 0 else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("סך הוצאות", f"${f_cost:,.2f}")
            c2.metric("קריאות API", f"{f_calls:,}")
            c3.metric("סך טוקנים", f"{f_tokens:,}")
            c4.metric("עלות ממוצעת לקריאה", f"${f_avg_cost:,.4f}")
            
            # 3. זיהוי חריגות (Anomalies) בתוך הפיצ'ר
            st.markdown("---")
            st.subheader("🚨 זיהוי חריגות ותנודתיות")
            feat_data['cost_per_call'] = feat_data['total_cost_usd'] / feat_data['calls']
            avg_feat_cost = feat_data['cost_per_call'].mean()
            
            # חריגה = יום שבו העלות לקריאה הייתה גבוהה ב-50% מהממוצע של אותו פיצ'ר
            anomalies = feat_data[feat_data['cost_per_call'] > (avg_feat_cost * 1.5)]
            
            if not anomalies.empty:
                st.error(f"⚠️ שימו לב: נמצאו {len(anomalies)} ימים עם חריגת עלויות (מעל 50% מהממוצע השוטף)!")
                st.dataframe(anomalies[['date', 'model', 'calls', 'total_cost_usd', 'cost_per_call']].style.format({
                    'date': '{:%Y-%m-%d}',
                    'total_cost_usd': '${:,.2f}',
                    'cost_per_call': '${:,.4f}'
                }), use_container_width=True)
            else:
                st.success("✅ לא זוהו חריגות משמעותיות בפיצ'ר זה בטווח התאריכים הנבחר.")
            
            # 4. כלי עזר: התייעצות אוטומטית עם AI
            st.markdown("---")
            st.subheader("🤖 התייעצות עם AI להסקת מסקנות")
            st.info("כדי לנתח את הנתונים לעומק, הופק עבורך פרומפט הכולל את נתוני הפיצ'ר. העתק אותו ופתח את הצ'אט.")
            
            # יצירת טקסט הנתונים להזרקה לפרומפט
            summary_csv = feat_data[['date', 'model', 'calls', 'total_cost_usd']].to_csv(index=False)
            
            ai_prompt = (
                f"היי, אני מנתח את ההוצאות של הפיצ'ר '{selected_feature}' במערכת ה-AI שלנו.\n"
                f"סה\"כ הוצאנו עליו ${f_cost:.2f} עבור {f_calls} קריאות.\n\n"
                f"הנה הנתונים הגולמיים (CSV):\n"
                f"{summary_csv}\n\n"
                f"המשימה שלך: נתח את המגמה. האם אתה מזהה בעיות יעילות או זללנות טוקנים בנקודות זמן מסוימות? "
                f"מה היית ממליץ לי לעשות כדי להוזיל עלויות בהנחה שאנחנו משתמשים במודלים האלו?"
            )
            
            # תיבת קוד עם כפתור העתקה מובנה
            st.code(ai_prompt, language="text")
            
            # כפתור לפתיחת ג'מיני
            st.markdown(
                """
                <a href="https://gemini.google.com/app" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #1f77b4; color: white; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    🚀 לחץ כאן למעבר ל-Gemini
                </a>
                """, 
                unsafe_allow_html=True
            )

    # --- לשונית 3: ניתוח לפי מודל ---
    with tab3:
        st.header("השוואת ביצועים ועלויות בין מודלים")
        
        model_grp = filtered_df.groupby('model').agg({
            'total_cost_usd': 'sum',
            'calls': 'sum'
        }).reset_index()
        
        col1, col2 = st.columns(2)
        with col1:
            fig_model_cost = px.bar(model_grp, x='model', y='total_cost_usd',
                                    title="סך הוצאות לפי מודל",
                                    color='model', color_discrete_sequence=COLORS)
            st.plotly_chart(fig_model_cost, use_container_width=True)
            
        with col2:
            fig_model_calls = px.pie(model_grp, values='calls', names='model', hole=0.4,
                                     title="נתח קריאות (API Calls) לפי מודל",
                                     color_discrete_sequence=COLORS)
            st.plotly_chart(fig_model_calls, use_container_width=True)

    # --- לשונית 4: כלכלה וחריגות ---
    with tab4:
        st.header("מעקב יעילות כלכלית וזיהוי חריגות")
        
        # חישוב עלות פר קריאה ברמת השורה
        filtered_df['cost_per_call'] = filtered_df['total_cost_usd'] / filtered_df['calls']
        
        # מציאת הימים/פיצ'רים היקרים ביותר (Top 10)
        st.subheader("🚨 10 הימים/הפיצ'רים היקרים ביותר בממוצע לקריאה")
        top_expensive = filtered_df.sort_values(by='cost_per_call', ascending=False).head(10)
        
        st.dataframe(top_expensive[['date', 'feature', 'model', 'calls', 'total_cost_usd', 'cost_per_call']].style.format({
            'date': '{:%Y-%m-%d}',
            'total_cost_usd': '${:,.2f}',
            'cost_per_call': '${:,.4f}'
        }), use_container_width=True)
        
        st.markdown("---")
        st.subheader("פירוט נתונים מלא (Raw Data)")
        st.dataframe(filtered_df, use_container_width=True)