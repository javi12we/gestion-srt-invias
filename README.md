# Gestión SRT

MVP interno para gestión de correspondencia con autenticación, roles y permisos usando Streamlit y MongoDB.

## Arranque rápido
1. Copia `.env.example` a `.env`
2. Ajusta la cadena de conexión a MongoDB
3. Define `ADMIN_INICIAL_PASSWORD` para que se cree el primer usuario `admin`
4. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
5. Inicializa la base de datos (colecciones, validadores, índices y catálogos):
   ```bash
   python -m app.scripts.init_db
   ```

6. Ejecuta la app:
   ```bash
   streamlit run app/main.py
   ```

## Nota
El usuario inicial `admin` se crea automáticamente si no existe:
- usuario: `admin`
- contraseña: la que definas en `ADMIN_INICIAL_PASSWORD`

Cámbialo apenas entres al sistema.

## Estado del MVP
Ya está incluida la base para:
- login seguro con hash de contraseña
- home inicial con resumen de permisos
- perfil del usuario con cambio de contraseña
- administración de usuarios (crear, editar, activar/desactivar)
- administración de roles con asignación de permisos
- bootstrap de Mongo con índices y validadores de esquema
- validación de permisos en backend (autorización)
- auditoría de cambios (usuario, rol, contraseña)
