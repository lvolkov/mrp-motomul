import streamlit as st
import pandas as pd

st.set_page_config(page_title="MRP.Мотомул", layout="wide")
st.title("🔍 MRP.Мотомул — Расчёт потребности")

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
        batch = float(row[COL_PARENT_QTY]) if pd.notna(row[COL_PARENT_QTY]) and row[COL_PARENT_QTY] != 0 else 1.0
        child = str(row[COL_CHILD]).strip()
        qty = float(row[COL_CHILD_QTY]) if pd.notna(row[COL_CHILD_QTY]) else 1.0
        
        if parent not in bom: bom[parent] = {}
        if child in bom[parent]:
            bom[parent][child]['qty'] += qty
        else:
            bom[parent][child] = {'qty': qty, 'batch': batch}
    return bom

def get_root_products(df_spec):
    all_parents = set(df_spec[COL_PARENT].unique())
    all_children = set(df_spec[COL_CHILD].unique())
    roots = all_parents - all_children
    return sorted(roots)

def calculate_mrp(bom, stock_df, root_product, plan_qty):
    stock_dict = dict(zip(stock_df[COL_STOCK_NAME], stock_df[COL_STOCK_QTY]))
    gross_req = {root_product: plan_qty}
    planned = {}
    levels = {root_product: 0}
    paths = {root_product: root_product}  # 🔥 Храним путь для каждого материала
    
    from collections import deque
    queue = deque([root_product])
    visited = set([root_product])
    all_items = [root_product]
    
    while queue:
        p = queue.popleft()
        if p in bom:
            for c in bom[p]:
                if c not in visited:
                    visited.add(c)
                    levels[c] = levels[p] + 1
                    paths[c] = f"{paths[p]} → {c}"  # 🔥 Строим путь
                    all_items.append(c)
                    queue.append(c)
                    
    all_items.sort(key=lambda x: levels[x])
    
    for item in all_items:
        gross = gross_req.get(item, 0)
        stock = stock_dict.get(item, 0)
        net = max(0, gross - stock)
        planned[item] = net
        
        if net > 0 and item in bom:
            for child, data in bom[item].items():
                ratio = data['qty'] / data['batch']
                need = net * ratio
                gross_req[child] = gross_req.get(child, 0) + need
                
    # 🔥 Добавляем путь в результат
    df_res = pd.DataFrame([{
        "Уровень": levels[i], 
        "Путь": paths.get(i, i),  # 🔥 Колонка Путь
        "Материал": i,
        "Валовая": round(gross_req.get(i,0),2), 
        "Остаток": stock_dict.get(i,0),
        "Дефицит": round(planned[i],2),
        "Действие": "🔨 Собрать" if i in bom else "🛒 Закупить",
        "Статус": "✅ OK" if planned[i]==0 else "❌ Дефицит"
    } for i in all_items])
    
    return df_res, levels

st.sidebar.header("📂 Данные")
specs_file = st.sidebar.file_uploader("📋 Спецификации", type=["xlsx"])
stock_file = st.sidebar.file_uploader("📦 Остатки из 1С", type=["xlsx"])

if specs_file and stock_file:
    df_spec = load_specs(specs_file)
    df_stock = load_and_map_stock(stock_file)
    
    if not df_stock.empty:
        bom = build_bom_dict(df_spec)
        root_products = get_root_products(df_spec)
        
        target_product = st.sidebar.selectbox("📦 Готовое изделие", root_products)
        target_qty = st.sidebar.number_input("📈 План", min_value=1, value=10)
        show_deficit = st.sidebar.checkbox("🔴 Только дефицит", value=True)

        if st.sidebar.button("🧮 Рассчитать"):
            df_res, levels = calculate_mrp(bom, df_stock, target_product, target_qty)
            
            if show_deficit:
                df_res = df_res[df_res["Дефицит"] > 0]
                
            df_res = df_res.sort_values(["Уровень", "Материал"]).reset_index(drop=True)
            
            if df_res.empty:
                st.success(f"🎉 Для {target_qty} шт. '{target_product}' материалов достаточно!")
            else:
                st.subheader(f"📦 Итог для {target_qty} ед. '{target_product}'")
                st.dataframe(df_res, use_container_width=True, hide_index=True)
                
                df_res.to_excel("mrp_final.xlsx", index=False)
                with open("mrp_final.xlsx", "rb") as f:
                    st.download_button("📥 Скачать", f, file_name="mrp_final.xlsx")
    else:
        st.warning("Файл остатков пуст.")
else:
    st.info("👆 Загрузи ОБА файла")