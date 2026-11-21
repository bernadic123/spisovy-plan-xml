import streamlit as st
import pandas as pd
import re
import random
import string
from xml.sax.saxutils import escape

UNUSED = "-- Nepoužít --"

def escapeXml(text):
    if pd.isna(text) or text is None:
        return ""
    return escape(str(text), {'"': chr(38) + 'quot;', "'": chr(38) + 'apos;'})

def auto_match(cols, keywords, exclude=None):
    for c in cols:
        cl = c.lower()
        if exclude and any(ex in cl for ex in exclude):
            continue
        if any(k in cl for k in keywords):
            return c
    return UNUSED

def generate_xml(df, col_map, params):
    cZnak = col_map["znak"]
    cNazev = col_map["nazev"]
    cSkZnak = col_map["sk_znak"]
    cSkLhuta = col_map["sk_lhuta"]
    cUdalost = col_map["udalost"]
    cPozn = col_map["poznamka"]

    if cZnak == UNUSED:
        raise ValueError("Musíte namapovat alespoň sloupec 'Plně určený spisový znak'.")

    parsedData = []
    for _, r in df.iterrows():
        val = r[cZnak]
        if pd.isna(val):
            continue
        znakVal = str(val).strip()
        if znakVal.endswith('.0'):
            znakVal = znakVal[:-2]
        if not znakVal:
            continue

        sk_lhuta_val = ""
        if cSkLhuta != UNUSED and pd.notna(r[cSkLhuta]):
            raw_val = str(r[cSkLhuta]).strip()
            match = re.search(r'\d+', raw_val)
            if match:
                sk_lhuta_val = match.group(0)

        parsedData.append({
            "znak": znakVal,
            "nazev": str(r[cNazev]).strip() if cNazev != UNUSED and pd.notna(r[cNazev]) else "",
            "skZnak": str(r[cSkZnak]).strip() if cSkZnak != UNUSED and pd.notna(r[cSkZnak]) else "",
            "skLhuta": sk_lhuta_val,
            "udalost": str(r[cUdalost]).strip() if cUdalost != UNUSED and pd.notna(r[cUdalost]) else "",
            "poznamka": str(r[cPozn]).strip() if cPozn != UNUSED and pd.notna(r[cPozn]) else ""
        })

    if not parsedData:
        raise ValueError("Ve vybraném sloupci pro spisový znak nebyla nalezena žádná data.")

    defDateFull = params['datum']
    defDateShort = defDateFull.split('T')[0]

    xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    xml += f'<SpisovyPlan xmlns="http://www.mvcr.cz/nsesss/v3" ID="{escapeXml(params["sp_id"])}">\n'
    xml += f'    <Identifikator zdroj="eSSL">{escapeXml(params["sp_ident"])}</Identifikator>\n'
    xml += f'    <Nazev>{escapeXml(params["sp_nazev"])}</Nazev>\n'
    xml += f'    <Manipulace>\n        <DatumOtevreni datum="{defDateFull}">{defDateShort}</DatumOtevreni>\n    </Manipulace>\n'
    xml += '    <Vydavatel>\n        <Subjekt>\n'
    xml += f'            <IdentifikatorOrganizace zdroj="IČ">{escapeXml(params["ico"])}</IdentifikatorOrganizace>\n'
    xml += f'            <NazevOrganizace>{escapeXml(params["org_nazev"])}</NazevOrganizace>\n'
    xml += f'            <SidloOrganizace>{escapeXml(params["sidlo"])}</SidloOrganizace>\n'
    xml += '        </Subjekt>\n    </Vydavatel>\n'

    currentPath = []
    baseIndent = 1

    def getIndent(extra=0):
        return "    " * (baseIndent + len(currentPath) + extra)

    for idx, row in enumerate(parsedData):
        plneUrceny = row["znak"]
        levels = [x for x in plneUrceny.split('.') if x]
        targetDepth = len(levels)

        while len(currentPath) > targetDepth - 1:
            currentPath.pop()
            xml += "    " * (baseIndent + len(currentPath)) + '</PlanVecnaSkupina>\n'

        ind = getIndent()
        id_str = escapeXml(f"VecnaSkupina_gen{idx + 1000}")
        xml += ind + f'<PlanVecnaSkupina ID="{id_str}">\n'
        currentPath.append(plneUrceny)

        ind2 = getIndent()
        ident = escapeXml(f"GenID{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}")
        nazev = escapeXml(row["nazev"])
        jednZnak = escapeXml(levels[-1])
        poznamka = escapeXml(row["poznamka"])
        skZnak = escapeXml(row["skZnak"])
        skLhuta = escapeXml(row["skLhuta"])
        spUdalostRaw = row["udalost"]

        is_externi = "extern" in spUdalostRaw.lower()
        if spUdalostRaw and spUdalostRaw.lower() != "nan":
            spUdalost = escapeXml(spUdalostRaw)
        else:
            spUdalost = "Rok uzavření spisu (vyřízení samostatného dokumentu)"

        skRezimId = escapeXml(f"xxxx{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}")
        akce = "Skartovat" if skZnak.upper() == 'S' else "Archivovat"
        if is_externi:
            skRezimNazev = escapeXml(f"{akce} {skLhuta} roků po externí události")
            komentar = poznamka if poznamka else "komentář"
        else:
            skRezimNazev = escapeXml(f"{akce} {skLhuta} roků po vyřízení dokumentu nebo uzavření spisu")
            komentar = "komentář"

        xml += ind2 + '<EvidencniUdaje>\n'
        xml += ind2 + f'    <Identifikace>\n{ind2}        <Identifikator zdroj="eSSL">{ident}</Identifikator>\n{ind2}    </Identifikace>\n'
        xml += ind2 + f'    <Popis>\n{ind2}        <Nazev>{nazev}</Nazev>\n{ind2}    </Popis>\n'

        if poznamka and poznamka.lower() != "nan":
            xml += ind2 + f'    <Poznamky>\n{ind2}        <Poznamka>{poznamka}</Poznamka>\n{ind2}    </Poznamky>\n'

        xml += ind2 + f'    <Puvod>\n{ind2}        <DatumVytvoreni datum="{defDateFull}">{defDateShort}</DatumVytvoreni>\n{ind2}    </Puvod>\n'
        xml += ind2 + f'    <Trideni>\n{ind2}        <JednoduchySpisovyZnak>{jednZnak}</JednoduchySpisovyZnak>\n{ind2}        <PlneUrcenySpisovyZnak>{plneUrceny}</PlneUrcenySpisovyZnak>\n{ind2}    </Trideni>\n'

        if skZnak and skZnak.lower() != "nan":
            xml += ind2 + '    <Vyrazovani>\n'
            xml += ind2 + '        <SkartacniRezim>\n'
            xml += ind2 + f'            <Identifikator zdroj="eSSL">{skRezimId}</Identifikator>\n'
            xml += ind2 + f'            <Nazev>{skRezimNazev}</Nazev>\n'
            xml += ind2 + f'            <Komentar>{komentar}</Komentar>\n'
            xml += ind2 + '            <Oduvodneni>podle platného skartačního rejstříku</Oduvodneni>\n'
            xml += ind2 + f'            <SkartacniZnak>{skZnak}</SkartacniZnak>\n'
            xml += ind2 + f'            <SkartacniLhuta>{skLhuta}</SkartacniLhuta>\n'
            xml += ind2 + f'            <SpousteciUdalost>{spUdalost}</SpousteciUdalost>\n'
            xml += ind2 + '        </SkartacniRezim>\n'
            xml += ind2 + '    </Vyrazovani>\n'
        else:
            xml += ind2 + '    <Vyrazovani/>\n'

        xml += ind2 + f'    <Manipulace>\n{ind2}        <DatumOtevreni datum="{defDateFull}">{defDateShort}</DatumOtevreni>\n{ind2}    </Manipulace>\n'
        xml += ind2 + '</EvidencniUdaje>\n'

    while len(currentPath) > 0:
        currentPath.pop()
        xml += "    " * (baseIndent + len(currentPath)) + '</PlanVecnaSkupina>\n'

    xml += '</SpisovyPlan>\n'
    return xml, len(parsedData)

# --- ROZHRANÍ STREAMLIT ---
st.set_page_config(page_title="Převodník Spisového plánu", layout="wide")
st.title("Převodník Excel → XML (NSESSS Spisový plán)")

with st.sidebar:
    st.header("Metadata spisového plánu")
    params = {
        "datum": st.text_input("Fixní Datum", "2025-01-01T08:00:07"),
        "sp_id": st.text_input("ID Spisového plánu", "SpisovyPlan_009"),
        "sp_ident": st.text_input("Identifikátor (eSSL)", "Alis93VZ67NQ"),
        "sp_nazev": st.text_input("Název plánu", "Spisový a skartační řád ZUŠ"),
        "ico": st.text_input("IČO Organizace", "00672416"),
        "org_nazev": st.text_input("Název Organizace", "Obec A L I S"),
        "sidlo": st.text_input("Sídlo Organizace", "Mariánská 538/21, Česká Lípa, 47001"),
    }

uploaded_file = st.file_uploader("1. Nahrajte Excel soubor (.xlsx nebo .xls)", type=["xlsx", "xls"])

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        col1, col2 = st.columns(2)
        with col1:
            sheet = st.selectbox("Vyberte list (Sheet)", xls.sheet_names)
        with col2:
            header_row = st.number_input("Řádek hlavičky (1 = první řádek)", min_value=1, max_value=30, value=1)

        df = pd.read_excel(uploaded_file, sheet_name=sheet, header=header_row - 1)
        cols = [str(c).strip() for c in df.columns]
        df.columns = cols
        options = [UNUSED] + cols

        st.subheader("2. Párování sloupců")
        m1, m2, m3 = st.columns(3)
        with m1:
            c_znak = st.selectbox("Plně určený spisový znak *", options, index=options.index(auto_match(cols, ["sp. znak", "sp.znak", "plně", "plne", "znak"], ["skart", "sk."])))
            c_nazev = st.selectbox("Název věcné skupiny", options, index=options.index(auto_match(cols, ["název", "nazev", "popis"])))
        with m2:
            c_sk_znak = st.selectbox("Skartační znak (S / A / V)", options, index=options.index(auto_match(cols, ["skartační znak", "skartacni znak", "sk. znak", "sk.znak"])))
            c_sk_lhuta = st.selectbox("Skartační lhůta", options, index=options.index(auto_match(cols, ["lhůta", "lhuta"])))
        with m3:
            c_udalost = st.selectbox("Spouštěcí událost", options, index=options.index(auto_match(cols, ["událost", "udalost", "spouštěcí", "spousteci"])))
            c_pozn = st.selectbox("Poznámka", options, index=options.index(auto_match(cols, ["poznámka", "poznamka"])))

        with st.expander("Náhled načtené tabulky (prvních 5 řádků)"):
            st.dataframe(df.head())

        col_map = {
            "znak": c_znak, "nazev": c_nazev, "sk_znak": c_sk_znak,
            "sk_lhuta": c_sk_lhuta, "udalost": c_udalost, "poznamka": c_pozn
        }

        if st.button("Vygenerovat XML", type="primary"):
            xml_output, count = generate_xml(df, col_map, params)
            st.success(f"Hotovo! Zpracováno {count} věcných skupin.")
            st.download_button(
                label="Stáhnout XML soubor",
                data=xml_output.encode("utf-8"),
                file_name="Vystup_SpisovyPlan.xml",
                mime="application/xml"
            )
    except Exception as e:
        st.error(f"Chyba při zpracování souboru: {e}")