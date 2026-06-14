import io
import tempfile
import os

import streamlit as st

from models import ProjectMetadata
from ba_project import BiologicalAssessment

st.set_page_config(page_title="ODOT Biological Assessment Tool", layout="centered")

st.title("ODOT Biological Assessment Tool")
st.caption("Automated data gathering for Biological Assessments")

# --- Project inputs ---
st.header("Project Information")
col1, col2 = st.columns(2)
with col1:
    jp_number = st.text_input("JP Number", placeholder="e.g. 38881(04)")
with col2:
    county = st.text_input("County", placeholder="e.g. McClain")
preparer = st.text_input("Preparer Name", placeholder="e.g. Jane Smith, Crafton Tull")

st.header("Project File")
kmz_file = st.file_uploader("Upload KMZ file", type=["kmz"])

run_ready = jp_number and county and kmz_file

st.markdown("""
<style>
.stButton > button[kind="primary"] {
    background-color: #57B847;
    border-color: #57B847;
}
.stButton > button[kind="primary"]:hover {
    background-color: #4aa33d;
    border-color: #4aa33d;
}
.stDownloadButton > button[kind="primary"] {
    background-color: #57B847;
    border-color: #57B847;
}
.stDownloadButton > button[kind="primary"]:hover {
    background-color: #4aa33d;
    border-color: #4aa33d;
}
</style>
""", unsafe_allow_html=True)

if st.button("Run Pipeline", disabled=not run_ready, type="primary"):
    st.session_state.pop("results", None)
    st.session_state.pop("docx_bytes", None)
    st.session_state.pop("filename", None)

    metadata = ProjectMetadata(jp_number=jp_number, county=county, preparer=preparer or None)
    ba = BiologicalAssessment(metadata)

    # Write KMZ to a temp file
    with tempfile.NamedTemporaryFile(suffix=".kmz", delete=False) as tmp:
        tmp.write(kmz_file.read())
        kmz_path = tmp.name

    st.subheader("Pipeline Progress")

    try:
        import pipeline_functions

        # Step 1: KMZ
        with st.spinner("Reading KMZ..."):
            kmz_result = pipeline_functions.ingest_kmz(kmz_path)
            ba.results['kmz_ingest'] = kmz_result
        if kmz_result.status == "error":
            st.error(f"KMZ ingest failed: {'; '.join(kmz_result.issues)}")
            st.stop()
        st.success(f"KMZ — {kmz_result.fields['acres'].value} ac")

        geojson_polygon = kmz_result.fields['geojson_polygon'].value

        # Step 2: IPaC
        with st.spinner("Querying IPaC..."):
            ipac_result = pipeline_functions.query_ipac(geojson_polygon)
            ba.results['ipac'] = ipac_result
        if ipac_result.status == "error":
            st.error(f"IPaC query failed: {'; '.join(ipac_result.issues)}")
            st.stop()
        n_species = len(ipac_result.fields.get('te_species', type('', (), {'value': []})()).value)
        st.success(f"IPaC — {n_species} TE species")

        # Step 3: NWI fallback if needed
        if 'wetlands' not in ipac_result.fields:
            with st.spinner("IPaC wetlands unavailable — querying NWI..."):
                nwi_result = pipeline_functions.query_nwi(geojson_polygon)
                ba.results['nwi'] = nwi_result
            if 'wetlands' in nwi_result.fields:
                ipac_result.fields['wetlands'] = nwi_result.fields['wetlands']
                st.success("NWI fallback — wetlands retrieved")
            else:
                st.warning("NWI fallback — no wetland data returned")

        # Step 4: SSURGO
        with st.spinner("Querying SSURGO soils..."):
            ssurgo_result = pipeline_functions.query_ssurgo(geojson_polygon)
            ba.results['ssurgo'] = ssurgo_result
        if ssurgo_result.issues:
            st.warning(f"SSURGO — {'; '.join(ssurgo_result.issues)}")
        else:
            n_soils = len(ssurgo_result.fields.get('soils', type('', (), {'value': []})()).value)
            st.success(f"SSURGO — {n_soils} soil map units")

        # Step 5: MLRA / Carter & Gregory
        with st.spinner("Querying MLRA and Carter & Gregory soils..."):
            mlra_result = pipeline_functions.query_mlra(geojson_polygon)
            ba.results['mlra'] = mlra_result
        mlra_field = mlra_result.fields.get('mlra')
        if mlra_result.issues:
            st.warning(f"MLRA — {'; '.join(mlra_result.issues)}")
        elif mlra_field:
            mv = mlra_field.value
            n_assoc = len(mv.get('associations', []))
            st.success(f"MLRA {mv['mlra_sym']} — {mv['mlra_name']} ({n_assoc} C&G association(s))")

        # Step 6: NHD
        with st.spinner("Querying NHD streams..."):
            nhd_result = pipeline_functions.query_nhd(geojson_polygon)
            ba.results['nhd'] = nhd_result
        if nhd_result.issues:
            st.warning(f"NHD — {'; '.join(nhd_result.issues)}")
        else:
            n_streams = len((nhd_result.fields.get('streams') or type('', (), {'value': []})()).value)
            st.success(f"NHD — {n_streams} stream feature(s)")

        # Step 6: Ecoregion
        with st.spinner("Querying ecoregion..."):
            ecoregion_result = pipeline_functions.query_ecoregion(geojson_polygon)
            ba.results['ecoregion'] = ecoregion_result
        eco = ecoregion_result.fields.get('ecoregion')
        if ecoregion_result.issues:
            st.warning(f"Ecoregion — {'; '.join(ecoregion_result.issues)}")
        elif eco:
            ev = eco.value
            st.success(f"Ecoregion — {ev['code'].upper()} {ev['name']}")

        # Generate output docx into a temp file, then read bytes
        with st.spinner("Generating Project Data Summary..."):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_doc:
                doc_path = tmp_doc.name
            out_result = pipeline_functions.generate_project_data_summary(ba, doc_path)

        if out_result.status == "error":
            st.error(f"Output generation failed: {'; '.join(out_result.issues)}")
            st.stop()

        with open(doc_path, "rb") as f:
            docx_bytes = f.read()
        os.unlink(doc_path)

        st.session_state['results'] = ba
        st.session_state['docx_bytes'] = docx_bytes
        st.session_state['filename'] = f"JP{jp_number}_{county}_ProjectDataSummary.docx"

    finally:
        os.unlink(kmz_path)

# --- Results ---
if 'results' in st.session_state:
    ba = st.session_state['results']
    ipac = ba.results.get('ipac')
    kmz = ba.results.get('kmz_ingest')
    ssurgo = ba.results.get('ssurgo')
    eco_result = ba.results.get('ecoregion')
    nhd_result = ba.results.get('nhd')
    mlra_result = ba.results.get('mlra')

    st.divider()
    st.subheader("Results Summary")

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Acreage", f"{kmz.fields['acres'].value} ac" if kmz else "—")

    te = ipac.fields.get('te_species') if ipac else None
    c2.metric("TE Species", len(te.value) if te else "—")

    wetlands = ipac.fields.get('wetlands') if ipac else None
    c3.metric("Wetland Records", len(wetlands.value) if wetlands else "—")

    soils = ssurgo.fields.get('soils') if ssurgo else None
    c4.metric("Soil Map Units", len(soils.value) if soils else "—")

    mlra_field = mlra_result.fields.get('mlra') if mlra_result else None
    c5.metric("MLRA", mlra_field.value['mlra_sym'] if mlra_field else "—")

    nhd_streams = nhd_result.fields.get('streams') if nhd_result else None
    c6.metric("Stream Features", len(nhd_streams.value) if nhd_streams else "—")

    eco_field = eco_result.fields.get('ecoregion') if eco_result else None
    eco_label = eco_field.value['code'].upper() if eco_field else "—"
    c7.metric("Ecoregion", eco_label)

    # TE Species table
    if te and te.value:
        st.markdown("**Threatened & Endangered Species**")
        st.dataframe(
            [{"Common Name": s['common_name'], "Scientific Name": s['scientific_name'],
              "Status": s['status'], "Critical Habitat": "Yes" if s['critical_habitat'] else "No"}
             for s in te.value],
            use_container_width=True, hide_index=True,
        )

    # Wetlands table
    if wetlands and wetlands.value:
        st.markdown("**Wetlands**")
        st.dataframe(
            [{"Name / Code": w.get('wetland_name') or w.get('nwi_code') or "—",
              "Acres": w.get('wetland_area')}
             for w in wetlands.value],
            use_container_width=True, hide_index=True,
        )

    # Issues
    all_issues = ba.get_issues()
    if all_issues:
        st.warning(f"{len(all_issues)} issue(s) flagged — see the downloaded report for details.")

    st.divider()
    st.download_button(
        label="Download Project Data Summary",
        data=st.session_state['docx_bytes'],
        file_name=st.session_state['filename'],
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        type="primary",
    )
