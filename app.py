import streamlit as st
import pandas as pd

st.set_page_config(page_title="MRP.Мотомул", layout="wide")
st.title("🏭 MRP.Мотомул — Агрегированный расчёт")

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

def get_products_by_level(df_spec, target_level=0):
    """Находит продукты на заданном уровне иерархии"""
    if target_level == 0:
        # Уровень 0: продукты, которые НЕ являются материалами (корневые)
        all_parents = set(df_spec[COL_PARENT].unique())
        all_children = set(df_spec[COL_CHILD].unique())
        root_products = all_parents - all_children
        return sorted(list(root_products))
    else:
        # Для других уровней нужно строить дерево — упрощённо: покажем все уникальные продукты
        return sorted(df_spec[COL_PARENT].unique())

def calculate_mrp_cascade(bom, stock_df, product, gross_qty, path="", level=0, visited=None):
    if visited is None: visited = set()
    if product in visited: return []
    visited.add(product)

    is_assembly = product in bom
    stock_qty = 0.0
    if not stock_df.empty:
        match = stock_df[stock_df[COL_STOCK_NAME] == product]
        if not match.empty:
            stock_qty = float(match.iloc[0][COL_STOCK_QTY])

    net_req = max(0.0, gross_qty - stock_qty)
    current_path = f"{path} → {product}" if path else product

    rows = [{
        "Уровень": level,
        "Путь": current_path,
        "Материал": product,
        "Валовая_потребность": round(gross_qty, 2),
        "Остаток": stock_qty,
        "Дефицит_нетто": round(net_req, 2),
        "Действие": "🔨 Собрать" if is_assembly else "🛒 Закупить",
        "Статус": "✅ OK" if net_req == 0 else "❌ Дефицит"
    }]

    if net_req > 0 and is_assembly:
        for item in bom[product]:
            child_gross = net_req * (item['qty'] / item['batch'])
            child_rows = calculate_mrp_cascade(bom, stock_df, item['material'], child_gross, current_path, level + 1, visited.copy())
            rows.extend(child_rows)
            
    return rows

st.sidebar.header("📂 Данные")
specs_file = st.sidebar.file_uploader("📋 Спецификации", type=["xlsx"])
stock_file = st.sidebar.file_uploader("📦 Остатки из 1С", type=["xlsx"])

if specs_file and stock_file:
    df_spec = load_specs(specs_file)
    df_stock = load_and_map_stock(stock_file)
    
    if not df_stock.empty:
        bom = build_bom_dict(df_spec)
        
        # 🔽 1. Сначала выбираем уровень продукта
        product_level = st.sidebar.selectbox("🔢 Уровень продукта", [0, 1, 2, 3, 4, 5])
        
        # 🔽 2. Фильтруем продукты по уровню
        available_products = get_products_by_level(df_spec, product_level)
        
        if not available_products:
            st.warning(f"❌ На уровне {product_level} нет продуктов")
        else:
            target_product = st.sidebar.selectbox(f"📦 Продукт (уровень {product_level})", available_products)
            target_qty = st.sidebar.number_input("📈 Планируемое кол-во", min_value=1, value=10)
            show_only_deficit = st.sidebar.checkbox("🔴 Показывать только дефицит", value=True)
            
            aggregation_mode = st.sidebar.radio("Режим отображения", 
                                                ["📊 Агрегировать по материалам", "🌳 Показать дерево"])
            
            level_filter = st.sidebar.selectbox("🔢 Фильтр результатов по уровню", ["Все"] + [str(i) for i in range(10)])

            if st.sidebar.button("🧮 Рассчитать"):
                with st.spinner("Считаю..."):
                    tree_data = calculate_mrp_cascade(bom, df_stock, target_product, target_qty, level=product_level)
                    
                    if tree_
                        df_res = pd.DataFrame(tree_data)
                        
                        # Убираем дубликаты
                        df_res = df_res.groupby(["Уровень", "Путь", "Материал"]).agg({
                            "Валовая_потребность": "sum",
                            "Остаток": "first",
                            "Дефицит_нетто": "sum",
                            "Действие": "first",
                            "Статус": lambda x: "❌ Дефицит" if any(s == "❌ Дефицит" for s in x) else "✅ OK"
                        }).reset_index()
                        
                        # Агрегация
                        if "Агрегировать" in aggregation_mode:
                            df_res = df_res.groupby("Материал").agg({
                                "Валовая_потребность": "sum",
                                "Остаток": "first",
                                "Дефицит_нетто": "sum",
                                "Действие": "first",
                                "Статус": lambda x: "❌ Дефицит" if any(s == "❌ Дефицит" for s in x) else "✅ OK",
                                "Путь": lambda x: f"{len(x)} мест использования" if len(x) > 1 else x.iloc[0],
                                "Уровень": "min"
                            }).reset_index()
                            df_res = df_res.sort_values("Дефицит_нетто", ascending=False)
                        else:
                            df_res = df_res.sort_values(["Уровень", "Путь"]).reset_index(drop=True)
                            if level_filter != "Все":
                                df_res = df_res[df_res["Уровень"] == int(level_filter)]
                        
                        if show_only_deficit:
                            df_res = df_res[df_res["Дефицит_нетто"] > 0]
                            
                        if df_res.empty:
                            st.success(f"🎉 Для {target_qty} шт. '{target_product}' материалов достаточно!")
                        else:
                            st.subheader(f"📊 Расчёт для {target_qty} ед.")
                            st.dataframe(df_res, use_container_width=True, hide_index=True)
                            
                            df_res.to_excel("mrp_result.xlsx", index=False)
                            with open("mrp_result.xlsx", "rb") as f:
                                st.download_button("📥 Скачать", f, file_name="mrp_result.xlsx")
                    else:
                        st.error("❌ Ошибка: нет данных для расчёта")
    else:
        st.warning("Файл остатков пуст.")
else:
    st.info("👆 Загрузи ОБА файла")