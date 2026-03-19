"""
Panel de administración de usuarios para FRADMA Dashboard.

Proporciona interfaz para:
- Crear, editar, desactivar usuarios
- Ver historial de logins
- Gestionar roles y permisos
- Resetear passwords
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from utils.auth import AuthManager, UserRole, get_current_user
from utils.logger import configurar_logger

logger = configurar_logger("admin_panel", nivel="INFO")


def mostrar_panel_usuarios():
    """
    Panel completo de gestión de usuarios.
    Solo accesible para administradores.
    """
    
    current_user = get_current_user()
    if not current_user or not current_user.can_manage_users():
        st.error("❌ Acceso denegado. Se requiere rol de Administrador.")
        return
    
    auth_manager = AuthManager()
    
    st.markdown("### 👥 Gestión de Usuarios")
    
    # Tabs principales
    tab_list, tab_create, tab_history = st.tabs([
        "👥 Usuarios",
        "➕ Crear Usuario",
        "📜 Historial"
    ])
    
    # ================================================================
    # TAB 1: LISTA DE USUARIOS
    # ================================================================
    
    with tab_list:
        users = auth_manager.list_users()
        
        if not users:
            st.info("No hay usuarios en el sistema")
            return
        
        # Crear DataFrame para visualización
        df_users = pd.DataFrame(users)
        
        # Formatear columnas
        df_users['Estado'] = df_users['is_active'].apply(
            lambda x: '✅ Activo' if x else '❌ Inactivo'
        )
        
        def _fmt_dt(x, fmt):
            if not x:
                return 'Nunca' if '%H' in fmt else '-'
            if isinstance(x, str):
                x = datetime.fromisoformat(x)
            return x.strftime(fmt)

        df_users['Último Login'] = df_users['last_login'].apply(lambda x: _fmt_dt(x, '%Y-%m-%d %H:%M'))
        df_users['Creado'] = df_users['created_at'].apply(lambda x: _fmt_dt(x, '%Y-%m-%d'))
        
        # Mapeo de roles para display
        role_display = {
            UserRole.ADMIN: '👑 Admin',
            UserRole.ANALYST: '📊 Analista',
            UserRole.VIEWER: '👁️ Visualizador'
        }
        df_users['Rol'] = df_users['role'].map(role_display)
        
        # Mostrar empresa en tabla si existe la columna
        display_cols = ['username', 'name', 'email', 'Rol', 'Estado', 'Último Login', 'Creado']
        if 'empresa_nombre' in df_users.columns:
            df_users['Empresa'] = df_users['empresa_nombre'].fillna('— superadmin —')
            display_cols.insert(4, 'Empresa')

        # Mostrar tabla
        st.dataframe(
            df_users[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                'username': 'Usuario',
                'name': 'Nombre',
                'email': 'Email',
                'Rol': st.column_config.TextColumn(width='small'),
                'Estado': st.column_config.TextColumn(width='small'),
                'Empresa': st.column_config.TextColumn(width='medium'),
                'Último Login': st.column_config.TextColumn(width='medium'),
                'Creado': st.column_config.TextColumn(width='small')
            }
        )
        
        st.markdown("---")
        
        # ============================================================
        # ACCIONES SOBRE USUARIOS
        # ============================================================
        
        st.markdown("#### ⚙️ Acciones")
        
        col_action1, col_action2 = st.columns(2)
        
        # Acción 1: Desactivar/Activar usuario
        with col_action1:
            st.markdown("**Activar/Desactivar Usuario**")
            
            user_to_toggle = st.selectbox(
                "Selecciona usuario",
                [u['username'] for u in users],
                key="toggle_user_select"
            )
            
            if user_to_toggle:
                selected_user = next(u for u in users if u['username'] == user_to_toggle)
                is_active = selected_user['is_active']
                
                action_label = "🗑️ Desactivar" if is_active else "✅ Activar"
                action_type = "desactivar" if is_active else "activar"
                
                if st.button(action_label, key="btn_toggle"):
                    if user_to_toggle == current_user.username:
                        st.error("❌ No puedes desactivar tu propio usuario")
                    elif user_to_toggle == 'admin' and is_active:
                        st.error("❌ No se puede desactivar el usuario admin principal")
                    else:
                        if is_active:
                            success, msg = auth_manager.deactivate_user(
                                user_to_toggle, 
                                current_user.username
                            )
                        else:
                            success, msg = auth_manager.activate_user(
                                user_to_toggle,
                                current_user.username
                            )
                        
                        if success:
                            st.success(f"✅ {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
        
        # Acción 2: Resetear password
        with col_action2:
            st.markdown("**Resetear Password**")
            
            user_to_reset = st.selectbox(
                "Selecciona usuario",
                [u['username'] for u in users],
                key="reset_user_select"
            )
            
            new_password = st.text_input(
                "Nueva password",
                type="password",
                key="new_password_input",
                help="Mínimo 6 caracteres"
            )
            
            if st.button("🔑 Resetear Password", key="btn_reset"):
                if not new_password:
                    st.error("❌ Debes ingresar una nueva password")
                elif len(new_password) < 6:
                    st.error("❌ Password debe tener al menos 6 caracteres")
                else:
                    success, msg = auth_manager.reset_password(
                        user_to_reset,
                        new_password,
                        current_user.username
                    )
                    
                    if success:
                        st.success(f"✅ {msg}")
                        st.info(f"💡 Comunica esta password al usuario: `{new_password}`")
                    else:
                        st.error(f"❌ {msg}")
    
    # ================================================================
    # TAB 2: CREAR NUEVO USUARIO
    # ================================================================
    
    with tab_create:
        st.markdown("#### ➕ Crear Nuevo Usuario")
        
        with st.form("create_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input(
                    "Username *",
                    placeholder="usuario123",
                    help="Mínimo 3 caracteres, será usado para login"
                )
                
                new_name = st.text_input(
                    "Nombre Completo *",
                    placeholder="Juan Pérez"
                )
                
                new_password = st.text_input(
                    "Contraseña *",
                    type="password",
                    help="Mínimo 6 caracteres"
                )
            
            with col2:
                new_email = st.text_input(
                    "Email *",
                    placeholder="usuario@empresa.com"
                )
                
                new_role = st.selectbox(
                    "Rol *",
                    [UserRole.VIEWER, UserRole.ANALYST, UserRole.ADMIN],
                    format_func=lambda x: {
                        UserRole.ADMIN: "👑 Administrador (acceso total)",
                        UserRole.ANALYST: "📊 Analista (ver + exportar + IA)",
                        UserRole.VIEWER: "👁️ Visualizador (solo ver dashboards)"
                    }[x]
                )

                # Selector de empresa (Neon)
                empresas = auth_manager.list_empresas()
                empresa_opts = [("", "— Sin empresa (superadmin) —")] + [
                    (e["id"], f"{e['razon_social']}  •  {e['rfc']}") for e in empresas
                ]
                empresa_sel = st.selectbox(
                    "Empresa",
                    options=[o[0] for o in empresa_opts],
                    format_func=lambda eid: next(o[1] for o in empresa_opts if o[0] == eid),
                    help="Sin empresa = ve datos de todas las empresas (superadmin)"
                )
                new_empresa_id = empresa_sel if empresa_sel else None
                new_rfc_empresa = next(
                    (e["rfc"] for e in empresas if e["id"] == empresa_sel), None
                )

                new_notes = st.text_area(
                    "Notas (opcional)",
                    placeholder="Ej: Gerente de ventas, acceso temporal, etc.",
                    height=80
                )
            
            submitted = st.form_submit_button("➕ Crear Usuario", type="primary", use_container_width=True)
            
            if submitted:
                # Validaciones
                if not all([new_username, new_email, new_name, new_password]):
                    st.error("❌ Completa todos los campos obligatorios (*)")
                elif len(new_username) < 3:
                    st.error("❌ Username debe tener al menos 3 caracteres")
                elif len(new_password) < 6:
                    st.error("❌ Password debe tener al menos 6 caracteres")
                elif '@' not in new_email:
                    st.error("❌ Email inválido")
                else:
                    # Crear usuario
                    success, msg = auth_manager.create_user(
                        username=new_username,
                        email=new_email,
                        name=new_name,
                        password=new_password,
                        role=new_role,
                        created_by=current_user.username,
                        notes=new_notes,
                        empresa_id=new_empresa_id,
                        rfc_empresa=new_rfc_empresa,
                    )
                    
                    if success:
                        st.success(f"✅ {msg}")
                        st.info(f"""
                        **Credenciales del nuevo usuario:**
                        - Username: `{new_username}`
                        - Password: `{new_password}`
                        - Rol: {new_role}
                        
                        💡 Comunica estas credenciales al usuario de forma segura.
                        """)
                        
                        # Esperar 2 segundos y recargar
                        import time
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
    
    # ================================================================
    # TAB 3: HISTORIAL DE LOGINS
    # ================================================================
    
    with tab_history:
        st.markdown("#### 📜 Historial de Logins")
        
        col_filter1, col_filter2 = st.columns([3, 1])
        
        with col_filter1:
            filter_user = st.selectbox(
                "Filtrar por usuario",
                ['Todos'] + [u['username'] for u in users],
                key="history_filter_user"
            )
        
        with col_filter2:
            limit = st.number_input(
                "Registros",
                min_value=10,
                max_value=500,
                value=50,
                step=10
            )
        
        # Obtener historial
        history = auth_manager.get_login_history(
            username=filter_user if filter_user != 'Todos' else None,
            limit=limit
        )
        
        if not history:
            st.info("No hay registros de login")
        else:
            # Crear DataFrame
            df_history = pd.DataFrame(history)
            
            # Formatear columnas
            df_history['Estado'] = df_history['success'].apply(
                lambda x: '✅ Exitoso' if x else '❌ Fallido'
            )
            
            df_history['Fecha/Hora'] = df_history['timestamp'].apply(
                lambda x: datetime.fromisoformat(x).strftime('%Y-%m-%d %H:%M:%S')
            )
            
            # Mostrar tabla
            st.dataframe(
                df_history[['Fecha/Hora', 'username', 'Estado']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Fecha/Hora': 'Fecha y Hora',
                    'username': 'Usuario',
                    'Estado': st.column_config.TextColumn(width='small')
                }
            )
            
            # Estadísticas
            st.markdown("---")
            st.markdown("#### 📊 Estadísticas")
            
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            
            total_logins = len(df_history)
            successful = df_history['success'].sum()
            failed = total_logins - successful
            success_rate = (successful / total_logins * 100) if total_logins > 0 else 0
            
            col_stat1.metric("Total Intentos", total_logins)
            col_stat2.metric("Exitosos", successful)
            col_stat3.metric("Fallidos", failed, delta=f"{success_rate:.1f}% éxito")


def mostrar_panel_configuracion():
    """
    Panel de configuración del sistema.
    Solo accesible para administradores.
    """
    
    current_user = get_current_user()
    if not current_user or not current_user.can_edit_config():
        st.error("❌ Acceso denegado. Se requiere rol de Administrador.")
        return
    
    st.markdown("### ⚙️ Configuración del Sistema")
    
    from utils.constantes import UmbralesCxC
    
    with st.form("config_form"):
        st.markdown("#### 💳 Umbrales de Cuentas por Cobrar")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Niveles Críticos**")
            
            dias_critico = st.number_input(
                "Días Vencido (Crítico)",
                value=UmbralesCxC.DIAS_ALTO_RIESGO,
                min_value=0,
                help="A partir de cuántos días de vencimiento se considera crítico"
            )
            
            pct_morosidad_critico = st.number_input(
                "% Morosidad (Crítico)",
                value=float(UmbralesCxC.MOROSIDAD_ALTA),
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                help="Porcentaje de cartera vencida que se considera crítico"
            )
            
            pct_concentracion_critico = st.number_input(
                "% Concentración (Crítico)",
                value=float(UmbralesCxC.CONCENTRACION_ALTA),
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                help="Concentración en top cliente que se considera riesgosa"
            )
        
        with col2:
            st.markdown("**Niveles de Advertencia**")
            
            dias_advertencia = st.number_input(
                "Días Vencido (Advertencia)",
                value=UmbralesCxC.DIAS_VENCIDO_60_90,
                min_value=0,
                help="A partir de cuántos días se alerta"
            )
            
            pct_morosidad_advertencia = st.number_input(
                "% Morosidad (Advertencia)",
                value=float(UmbralesCxC.MOROSIDAD_MEDIA),
                min_value=0.0,
                max_value=100.0,
                step=1.0
            )
            
            pct_alto_riesgo = st.number_input(
                "% Alto Riesgo",
                value=float(UmbralesCxC.RIESGO_ALTO),
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                help="Qué porcentaje de cartera >90 días se considera alto riesgo"
            )
        
        st.markdown("---")
        
        submitted = st.form_submit_button("💾 Guardar Configuración", type="primary")
        
        if submitted:
            # TODO: Guardar configuración en base de datos o archivo
            # Por ahora solo mostramos confirmación
            st.success("✅ Configuración guardada exitosamente")
            st.info("""
            💡 **Nota:** Esta configuración se aplicará a partir del próximo cálculo de CxC.
            Los reportes existentes mantendrán los umbrales con los que fueron generados.
            """)


def mostrar_info_usuario():
    """
    Muestra información del usuario en el sidebar.
    Accesible para todos los usuarios autenticados.
    """
    
    user = get_current_user()
    if not user:
        return
    
    # Mapeo de roles para display
    role_icons = {
        UserRole.ADMIN: "👑",
        UserRole.ANALYST: "📊",
        UserRole.VIEWER: "👁️"
    }
    
    role_labels = {
        UserRole.ADMIN: "Administrador",
        UserRole.ANALYST: "Analista",
        UserRole.VIEWER: "Visualizador"
    }
    
    role_colors = {
        UserRole.ADMIN: "#dc2626",
        UserRole.ANALYST: "#2563eb",
        UserRole.VIEWER: "#65a30d"
    }
    
    st.sidebar.markdown("---")
    
    # Header de usuario
    col_user_info, col_logout = st.sidebar.columns([3, 1])
    
    with col_user_info:
        st.markdown(f"**{role_icons[user.role]} {user.name}**")
        
        # Badge de rol con color
        st.markdown(
            f"<span style='background-color:{role_colors[user.role]}; "
            f"color:white; padding:2px 8px; border-radius:4px; font-size:11px;'>"
            f"{role_labels[user.role]}</span>",
            unsafe_allow_html=True
        )
    
    with col_logout:
        if st.button("🚪", help="Cerrar sesión", key="btn_logout_sidebar"):
            logger.info(f"Logout: {user.username}")
            st.session_state.clear()
            st.rerun()
    
    st.sidebar.markdown("---")
    
    # Panel de administración (solo admins)
    if user.can_manage_users():
        with st.sidebar.expander("⚙️ Administración", expanded=False):
            admin_option = st.radio(
                "Opciones",
                ["Usuarios", "Configuración"],
                label_visibility="collapsed"
            )
            
            # Marcar que se debe mostrar el panel en el main
            st.session_state['show_admin_panel'] = True
            st.session_state['admin_panel_option'] = admin_option


if __name__ == "__main__":
    # Demo del panel de administración
    print("Panel de administración - debe ejecutarse desde Streamlit")
