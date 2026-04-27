import streamlit as st
import pandas as pd

st.set_page_config(page_title="MRP.Мотомул", layout="wide")
st.title("🏭 MRP.Мотомул — Корректный расчёт дефицита")

COL_PARENT = "Продукт"
COL_PARENT_QTY = "Кол_во_продукта"
COL_CHILD = "Материал"
COL_CHILD_QTY = "Кол_во_материала"

COL_STOCK_NAME = "Номенклатура"
COL_STOCK_QTY = "Остаток"

@st.cache_data
def load_specs(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.replace(' ', '')
    return df

def load_and_map_stock(file):
    df = pd.read_excel(file)
    df.columns = [str(c).strip() for c in df.columns]
    mapping = {}
    for col in df.columns:
        lower = col.lower()
        if any(kw in lower for kw in ["номенклатура", "наименование", "материал", "артикул"]):
            mapping[col] = COL_STOCK_NAME
        elif any(kw in lower for kw in ["остаток", "количество", "кол-", "в наличии", "qty"]):
            mapping[col] = COL_STOCK_QTY
    return df.rename(columns=mapping) if COL_STOCK_NAME in mapping.values() else pd.DataFrame()

def build_bom_dict(df_spec):
    bom = {}
    for _, row in df_spec.iterrows():
        parent = str(row[COL_PARENT]).strip()
        parent_qty = float(row[COL_PARENT_QTY]) if pd.notna(row[COL_PARENT_QTY]) else 1.0
        child = str(row[COL_CHILD]).strip()
        child_qty = float(row[COL_CHILD_QTY]) if pd.notna(row[COL_CHILD_QTY]) else 1.0
        bom.setdefault(parent, []).append({'material': child, 'qty': child_qty, 'batch': parent_qty})
    return bom

def explode_bom(bom, product, qty, path="", visited=None):
    if visited is None: visited = set()
    if product in visited: return {}
    visited.add(product)
    
    reqs = {product: {'qty': qty, 'path': path}}
    
    if product in bom:
        for item in bom[product]:
            child_need = qty * (item['qty'] / item['batch'])
            child_path = f"{path} → {item['material']}" if path else item['material']
            child_reqs = explode_bom(bom, item['material'], child_need, child_path, visited.copy())
            
            for mat, data in child_reqs.items():
                if mat in reqs:
                    reqs[mat]['qty'] += data['qty']
                else:
                    reqs[mat] = data
    return reqs

st.sidebar.header("📂 Данные")
specs_file = st.sidebar.file_uploader("📋 Спецификации", type=["xlsx"])
stock_file = st.sidebar.file_uploader("📦 Остатки из 1С", type=["xlsx"])

if specs_file and stock_file:
    df_spec = load_specs(specs_file)
    df_stock = load_and_map_stock(stock_file)
    
    if not df_stock.empty:
        bom = build_bom_dict(df_spec)
        products = sorted(df_spec[COL_PARENT].unique())
        
        target_product = st.sidebar.selectbox("📦 Продукт", products)
        target_qty = st.sidebar.number_input("📈 Планируемое кол-во", min_value=1, value=10)
        
        # ✅ ВЕРНУЛ ФИЛЬТР
        show_only_deficit = st.sidebar.checkbox("🔴 Показывать только дефицит", value=True)

        if st.sidebar.button("🧮 Рассчитать MRP"):
            with st.spinner("Агрегирую потребность и сверяю со складом..."):
                gross_needs = explode_bom(bom, target_product, target_qty)
                
                results = []
                for mat, data in gross_needs.items():
                    stock_row = df_stock[df_stock[COL_STOCK_NAME] == mat]
                    stock_qty = float(stock_row[COL_STOCK_QTY].iloc[0]) if not stock_row.empty else 0.0
                    
                    total_need = data['qty']
                    deficit = max(0, total_need - stock_qty)
                    
                    results.append({
                        "Материал": mat,
                        "Общая потребность": round(total_need, 3),
                        "Остаток на складе": stock_qty,
                        "Дефицит": round(deficit, 3),
                        "Статус": "✅ Хватает" if deficit == 0 else "🛒 Закупить",
                        "Где используется": data['path']
                    })
                
                df_res = pd.DataFrame(results)
                
                # 🔴 ФИЛЬТРАЦИЯ
                if show_only_deficit:
                    df_res = df_res[df_res["Дефицит"] > 0]
                
                df_res = df_res.sort_values("Дефицит", ascending=False).reset_index(drop=True)
                
                if df_res.empty:
                    st.success(f"🎉 Для {target_qty} шт. '{target_product}' всех материалов достаточно!")
                else:
                    st.subheader(f"📊 MRP-отчёт для {target_qty} ед. '{target_product}'")
                    st.dataframe(df_res, use_container_width=True, hide_index=True)
                    
                    df_res.to_excel("mrp_netting_result.xlsx", index=False)
                    with open("mrp_netting_result.xlsx", "rb") as f:
                        st.download_button("📥 Скачать отчёт", f, file_name="mrp_netting_result.xlsx")
    else:
        st.warning("Файл остатков пуст или не распознан.")
else:
    st.info("👆 Загрузи ОБА файла")