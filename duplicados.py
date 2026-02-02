import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
from pathlib import Path

st.set_page_config(
    page_title="Procesador de Duplicados",
    page_icon="📊",
    layout="wide"
)

# Función para mostrar diagnóstico
def mostrar_diagnostico(df, archivo_nombre):
    """Muestra información de diagnóstico del archivo"""
    st.markdown("---")
    st.subheader("📋 Diagnóstico del Archivo")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Registros", f"{len(df):,}")
    with col2:
        st.metric("Columnas", len(df.columns))
    with col3:
        st.metric("Tamaño en memoria", f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
    
    # Mostrar información de columnas
    with st.expander("Ver columnas disponibles"):
        st.write("**Columnas en el archivo:**")
        for i, col in enumerate(df.columns, 1):
            st.write(f"{i}. `{col}`")
    
    # Mostrar tipos de datos
    with st.expander("Ver tipos de datos"):
        tipo_datos = pd.DataFrame({
            'Columna': df.columns,
            'Tipo': df.dtypes.astype(str),
            'No nulos': df.notna().sum(),
            'Nulos': df.isna().sum()
        })
        st.dataframe(tipo_datos, use_container_width=True)

# Función para procesar el archivo
def procesar_duplicados(df):
    """Procesa el archivo eliminando duplicados"""
    
    # Mostrar progreso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("📥 Cargando datos...")
    progress_bar.progress(10)
    
    # Guardar nombres originales
    nombres_originales = list(df.columns)
    
    # Normalizar nombres de columnas
    status_text.text("🔄 Normalizando nombres de columnas...")
    df.columns = df.columns.str.strip().str.lower()
    progress_bar.progress(20)
    
    # Verificar columnas necesarias
    columnas_necesarias = ['docto ident', 'f ingreso']
    columnas_faltantes = [col for col in columnas_necesarias if col not in df.columns]
    
    # Si faltan columnas, intentar mapeo automático
    if columnas_faltantes:
        status_text.text("🔍 Buscando columnas necesarias...")
        
        mapeo_encontrado = {}
        for necesaria in columnas_faltantes:
            necesaria_limpia = necesaria.replace(' ', '').lower()
            
            for disponible in df.columns:
                disponible_limpia = disponible.replace(' ', '').lower()
                
                # Buscar coincidencias flexibles
                if (necesaria_limpia in disponible_limpia or 
                    disponible_limpia in necesaria_limpia or
                    ('ident' in disponible and 'doc' in disponible and necesaria == 'docto ident') or
                    ('fecha' in disponible and ('ingreso' in disponible or 'entrada' in disponible) and necesaria == 'f ingreso')):
                    
                    mapeo_encontrado[necesaria] = disponible
        
        if mapeo_encontrado:
            st.info(f"Se encontraron posibles coincidencias: {mapeo_encontrado}")
            
            # Crear checkboxes para confirmar mapeos
            mapeo_aplicar = {}
            for necesaria, disponible in mapeo_encontrado.items():
                if st.checkbox(f"Usar '{disponible}' como '{necesaria}'", value=True, key=f"map_{necesaria}"):
                    mapeo_aplicar[necesaria] = disponible
            
            if mapeo_aplicar:
                for necesaria, disponible in mapeo_aplicar.items():
                    df[necesaria] = df[disponible]
                st.success("Mapeos aplicados correctamente")
            else:
                st.error("No se aplicaron mapeos. No se puede continuar.")
                return None
        else:
            st.error(f"No se pudieron encontrar las columnas: {columnas_faltantes}")
            
            # Mostrar sugerencias
            st.write("**Columnas disponibles:**")
            for i, col in enumerate(df.columns, 1):
                st.write(f"{i}. `{col}`")
            
            # Permitir mapeo manual
            st.subheader("Mapeo Manual")
            mapeo_manual = {}
            for necesaria in columnas_faltantes:
                col_seleccionada = st.selectbox(
                    f"Selecciona columna para '{necesaria}'",
                    options=[''] + list(df.columns),
                    key=f"manual_{necesaria}"
                )
                if col_seleccionada:
                    mapeo_manual[necesaria] = col_seleccionada
            
            if len(mapeo_manual) == len(columnas_faltantes):
                for necesaria, disponible in mapeo_manual.items():
                    df[necesaria] = df[disponible]
            else:
                return None
    
    progress_bar.progress(40)
    status_text.text("📅 Procesando fechas...")
    
    # Convertir fecha a datetime
    df['f ingreso'] = pd.to_datetime(df['f ingreso'], errors='coerce')
    sin_fecha = df['f ingreso'].isna().sum()
    
    if sin_fecha > 0:
        st.warning(f"⚠️ {sin_fecha:,} registros sin fecha válida")
    
    # Contar duplicados iniciales
    progress_bar.progress(60)
    status_text.text("🔍 Identificando duplicados...")
    
    duplicados_iniciales = df.duplicated(subset=['docto ident'], keep=False).sum()
    documentos_duplicados = df[df.duplicated(subset=['docto ident'], keep=False)]['docto ident'].nunique()
    
    # Ordenar y eliminar duplicados
    progress_bar.progress(80)
    status_text.text("🧹 Eliminando duplicados...")
    
    df_ordenado = df.sort_values(['docto ident', 'f ingreso'], 
                                ascending=[True, False], 
                                na_position='last')
    
    df_unico = df_ordenado.drop_duplicates(subset=['docto ident'], keep='first')
    
    # Ordenar resultado final
    if 'empleado' in df_unico.columns:
        df_resultado = df_unico.sort_values(['empleado', 'f ingreso'])
    else:
        df_resultado = df_unico.sort_values(['docto ident'])
    
    # Restaurar nombres originales
    columnas_originales = []
    for col in df_resultado.columns:
        if col in nombres_originales:
            columnas_originales.append(col)
        else:
            # Buscar columna original correspondiente
            for orig in nombres_originales:
                if orig.strip().lower() == col:
                    columnas_originales.append(orig)
                    break
            else:
                columnas_originales.append(col)
    
    df_resultado.columns = columnas_originales
    
    progress_bar.progress(100)
    status_text.text("✅ Procesamiento completado")
    
    # Mostrar estadísticas
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Registros Originales", f"{len(df):,}")
    with col2:
        st.metric("Registros Finales", f"{len(df_resultado):,}")
    with col3:
        duplicados_eliminados = len(df) - len(df_resultado)
        st.metric("Duplicados Eliminados", f"{duplicados_eliminados:,}")
    with col4:
        if len(df) > 0:
            reduccion = (duplicados_eliminados / len(df)) * 100
            st.metric("Reducción", f"{reduccion:.1f}%")
    
    # Mostrar detalles de duplicados
    with st.expander("📊 Detalles de duplicados identificados"):
        st.write(f"Documentos con duplicados: {documentos_duplicados:,}")
        st.write(f"Registros duplicados totales: {duplicados_iniciales:,}")
        
        if documentos_duplicados > 0:
            # Mostrar algunos documentos duplicados
            dup_docs = df[df.duplicated(subset=['docto ident'], keep=False)]['docto ident'].unique()[:10]
            st.write("**Primeros 10 documentos con duplicados:**")
            for doc in dup_docs:
                count = df[df['docto ident'] == doc].shape[0]
                st.write(f"- `{doc}`: {count} registros")
    
    return df_resultado

# Interfaz principal de Streamlit
def main():
    st.title("📊 Procesador de Duplicados Charyth")
    st.markdown("---")
    
    # Sidebar para configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        st.subheader("Opciones de Procesamiento")
        mantener_original = st.checkbox("Mantener columnas originales", value=True)
        agregar_timestamp = st.checkbox("Agregar timestamp al nombre", value=True)
        
        st.markdown("---")
        st.subheader("Información")
        st.write("Esta herramienta elimina duplicados basándose en:")
        st.write("1. **'DOCTO IDENT'** - Documento de identificación")
        st.write("2. **'F INGRESO'** - Fecha de ingreso")
        st.write("")
        st.write("Se conserva el registro con la fecha más reciente.")
    
    # Área principal
    st.subheader("📤 Sube tu archivo Excel")
    
    uploaded_file = st.file_uploader(
        "Arrastra y suelta tu archivo aquí",
        type=['xlsx', 'xls'],
        help="Solo archivos Excel (.xlsx, .xls)"
    )
    
    if uploaded_file is not None:
        try:
            # Leer el archivo
            df = pd.read_excel(uploaded_file)
            
            # Mostrar información del archivo
            mostrar_diagnostico(df, uploaded_file.name)
            
            # Botón para procesar
            if st.button("🚀 Procesar Duplicados", type="primary", use_container_width=True):
                with st.spinner("Procesando..."):
                    resultado = procesar_duplicados(df)
                    
                    if resultado is not None:
                        # Preparar archivo para descarga
                        st.markdown("---")
                        st.subheader("📥 Descargar Resultado")
                        
                        # Generar nombre de archivo
                        nombre_base = os.path.splitext(uploaded_file.name)[0]
                        if agregar_timestamp:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            nombre_descarga = f"Resultado_{nombre_base}_{timestamp}.xlsx"
                        else:
                            nombre_descarga = f"Resultado_{nombre_base}.xlsx"
                        
                        # Crear buffer para el Excel
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            resultado.to_excel(writer, index=False, sheet_name='Resultado')
                        
                        output.seek(0)
                        
                        # Botón de descarga
                        st.download_button(
                            label="⬇️ Descargar Archivo Procesado",
                            data=output,
                            file_name=nombre_descarga,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                        # Mostrar vista previa
                        st.markdown("---")
                        st.subheader("👁️ Vista Previa del Resultado")
                        
                        # Seleccionar columnas para mostrar
                        columnas_comunes = ['EMPLEADO', 'DOCTO IDENT', 'F INGRESO', 'NOMBRE', 'APELLIDO', 'CEDULA', 'DOCUMENTO']
                        columnas_disponibles = [col for col in columnas_comunes if col in resultado.columns]
                        
                        if columnas_disponibles:
                            # Usar las columnas disponibles más algunas extras
                            columnas_a_mostrar = columnas_disponibles[:5]
                            columnas_extra = [col for col in resultado.columns if col not in columnas_comunes][:3]
                            columnas_a_mostrar.extend(columnas_extra)
                            
                            vista_previa = resultado[columnas_a_mostrar].head(10)
                        else:
                            vista_previa = resultado.head(10)
                        
                        st.dataframe(vista_previa, use_container_width=True)
                        
                        # Mostrar estadísticas finales
                        st.success(f"✅ Procesamiento completado exitosamente")
                        
        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {str(e)}")
            st.info("""
            **Posibles soluciones:**
            1. Verifica que el archivo no esté dañado
            2. Asegúrate de que sea un archivo Excel válido
            3. Verifica que no esté protegido con contraseña
            4. Intenta guardar el archivo como .xlsx (Excel moderno)
            """)
    
    else:
        # Mostrar instrucciones cuando no hay archivo
        st.info("👆 Por favor, sube un archivo Excel para comenzar")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 📝 Requisitos del Archivo
            
            **Columnas necesarias:**
            - `DOCTO IDENT` (o similar)
            - `F INGRESO` (o similar)
            
            **Formatos soportados:**
            - Excel (.xlsx, .xls)
            - Máximo 100MB
            """)
        
        with col2:
            st.markdown("""
            ### 🎯 Qué hace la herramienta
            
            1. **Identifica duplicados** por documento
            2. **Conserva el más reciente** por fecha
            3. **Ordena resultados** por empleado
            4. **Genera nuevo archivo** limpio
            
            **Resultado:**
            - Archivo sin duplicados
            - Datos ordenados
            - Estadísticas detalladas
            """)
        
        # Ejemplo de estructura
        with st.expander("📋 Ver ejemplo de estructura esperada"):
            ejemplo_data = {
                'EMPLEADO': ['Juan Pérez', 'María García', 'Juan Pérez', 'Carlos López'],
                'DOCTO IDENT': ['123456', '789012', '123456', '345678'],
                'F INGRESO': ['2023-01-15', '2023-02-20', '2023-03-10', '2023-01-05'],
                'DEPARTAMENTO': ['Ventas', 'RH', 'Ventas', 'IT']
            }
            ejemplo_df = pd.DataFrame(ejemplo_data)
            st.dataframe(ejemplo_df, use_container_width=True)
            st.caption("En este ejemplo, Juan Pérez aparece dos veces con el mismo documento. Se conservará el registro con fecha 2023-03-10.")

if __name__ == "__main__":
    main()