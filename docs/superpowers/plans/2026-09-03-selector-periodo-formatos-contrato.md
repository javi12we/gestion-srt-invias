# Selector de período (año/mes) para Formatos de contrato y Sup. Formatos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que el contratista (en "Formatos de contrato") y el supervisor (en "Sup. Formatos") naveguen un dropdown de año/mes para generar, firmar o descargar cualquiera de los 8 formatos de un período pasado, en vez de operar solo sobre el período certificable actual calculado automáticamente.

**Architecture:** Se introduce el concepto de "período seleccionado" que por defecto es `CertificacionService.periodo_certificable()` (sin cambio de comportamiento) pero puede sobreescribirse. Todos los métodos de `CertificacionService` que hoy recalculan el período internamente ganan parámetros opcionales `año`/`mes`; dos nuevos helpers (`periodos_disponibles_usuario`, `periodos_disponibles_global`) generan las opciones del dropdown a partir de los contratos ya existentes; un helper de leyenda unificado (`leyenda_periodo`) reemplaza los mensajes hardcodeados de "mes anterior". Las páginas Streamlit (`6_certificaciones.py`, `admin_firmantes.py`) agregan el `st.selectbox` y pasan el período elegido a las funciones que ya recibían `año_cert`/`mes_cert` como parámetro (no todas lo hacían — hay que threadearlo también en las llamadas internas a servicio).

**Tech Stack:** Streamlit, PyMongo, patrones ya presentes en `app/services/certificacion_service.py`.

**Spec:** `docs/superpowers/specs/2026-09-03-selector-periodo-formatos-contrato-design.md` — léelo antes de empezar, cada tarea implementa una sección de ese documento.

## Global Constraints

- **Sin suite de pruebas automatizada** (ver CLAUDE.md — proyecto en etapa MVP). Este plan NO introduce pytest/mongomock. Cada tarea se verifica manualmente ejecutando `streamlit run app/main.py` contra la base de datos configurada en `.env`, o con un script `python -c` puntual cuando el método no depende de la UI. No inventes infraestructura de tests nueva.
- **Retrocompatibilidad estricta:** todo parámetro `año`/`mes` nuevo en `CertificacionService` debe ser opcional (`= None`) y caer a `self.periodo_certificable()` si no se pasa. Ningún llamador existente que no pase el período debe cambiar de comportamiento.
- Sigue los patrones de capas del proyecto: páginas → services → repositories → MongoDB. No hay cambios de esquema ni de repositorio en este plan — `certificaciones` ya tiene `año`/`mes` indexados y los métodos de `CertificacionRepositorio` ya aceptan `año`/`mes` explícitos.
- No se toca `app/pages_admin/admin_certificaciones.py` ("Seguimiento - Formatos") — queda fuera de alcance (ver spec). Sus llamadas a `obtener_empleados_para_certificar()`/`periodo_certificable()` sin argumentos deben seguir funcionando exactamente igual después de este plan (verificar en Task 3).
- Commits frecuentes: uno por tarea, mensaje en español, sigue el estilo de `git log --oneline -10`.

---

### Task 1: Helpers de período nuevos en `CertificacionService`

**Files:**
- Modify: `app/services/certificacion_service.py:93-97` (después de `es_periodo_abierto`, antes de la sección "Consultas de certificaciones")
- Modify: `app/services/certificacion_service.py:740-741` (después de `_contrato_para_periodo`, antes de `generar_pdf`)

**Interfaces:**
- Produces: `periodos_disponibles_usuario(usuario_id: str) -> List[tuple]`, `periodos_disponibles_global() -> List[tuple]`, `leyenda_periodo(año: int, mes: int) -> str`, `_contrato_relevante(contratos: list, año: int, mes: int) -> dict`. Usados por Task 2, 3, 4 y 5.

- [ ] **Step 1: Agregar los helpers de rango de períodos y la leyenda**

En `app/services/certificacion_service.py`, inmediatamente después de `es_periodo_abierto` (línea 93-96) y antes del comentario `# Consultas de certificaciones` (línea 98), agrega:

```python
    def _construir_rango_periodos(self, contratos: list) -> List[tuple]:
        """Genera la lista descendente de (año, mes) desde el mes de inicio del
        contrato más antiguo (fecha_inicio) hasta el período certificable actual,
        ambos inclusive. Si no hay contratos con fecha_inicio, devuelve solo el
        período certificable actual."""
        año_max, mes_max = self.periodo_certificable()

        fechas_inicio = [c.get("fecha_inicio") for c in contratos if c.get("fecha_inicio")]
        if not fechas_inicio:
            return [(año_max, mes_max)]

        fecha_min = min(fechas_inicio)
        if fecha_min.tzinfo is None:
            fecha_min = fecha_min.replace(tzinfo=timezone.utc)
        fecha_min_bogota = fecha_min.astimezone(ZONA_BOGOTA)
        año_min, mes_min = fecha_min_bogota.year, fecha_min_bogota.month

        periodos = []
        año, mes = año_max, mes_max
        while (año, mes) >= (año_min, mes_min):
            periodos.append((año, mes))
            mes -= 1
            if mes == 0:
                mes = 12
                año -= 1
        return periodos

    def periodos_disponibles_usuario(self, usuario_id: str) -> List[tuple]:
        """Períodos (año, mes) seleccionables por este contratista en 'Formatos de
        contrato': desde el inicio de su contrato más antiguo hasta el período
        certificable actual, orden descendente (más reciente primero)."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        usuario = UsuarioRepositorio().buscar_por_id(usuario_id)
        contratos = (usuario.get("contratos") or []) if usuario else []
        return self._construir_rango_periodos(contratos)

    def periodos_disponibles_global(self) -> List[tuple]:
        """Períodos (año, mes) seleccionables en 'Sup. Formatos': desde el contrato
        más antiguo registrado en todo el sistema hasta el período certificable
        actual, orden descendente."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        todos_contratos = []
        for usuario in UsuarioRepositorio().listar():
            todos_contratos.extend(usuario.get("contratos") or [])
        return self._construir_rango_periodos(todos_contratos)

    def leyenda_periodo(self, año: int, mes: int) -> str:
        """Texto coherente con el período efectivamente indicado: el actual, el mes
        anterior dentro de la ventana automática de gracia, o un período pasado
        elegido manualmente. Reemplaza los mensajes hardcodeados que asumían que el
        único período posible era 'hoy' o 'el mes anterior automático'."""
        nombre_mes = MESES_ES[mes - 1]
        if (año, mes) == self.periodo_certificable():
            if self.es_mes_anterior():
                dia_cierre = self._dia_inicio_periodo() - 1
                return (
                    f"Período anterior — {nombre_mes} {año} "
                    f"(ponerse al día, disponible hasta el día {dia_cierre} del mes en curso)"
                )
            return f"Período actual — {nombre_mes} {año}"
        return f"Período pasado — {nombre_mes} {año} (gestión retroactiva)"

```

En `app/services/certificacion_service.py`, inmediatamente después de `_contrato_para_periodo` (termina en la línea 740 con `return pool[0]`) y antes de `def generar_pdf`, agrega:

```python
    def _contrato_relevante(self, contratos: list, año: int, mes: int) -> dict:
        """Contrato a usar para mostrar/validar en el período (año, mes): el vigente
        hoy en tiempo real si es el período certificable actual (preserva el
        comportamiento exacto de hoy cuando nadie toca el selector), o el vigente
        históricamente en ese año/mes si es un período pasado elegido manualmente."""
        if (año, mes) == self.periodo_certificable():
            return self._contrato_vigente(contratos)
        return self._contrato_para_periodo(contratos, año, mes)

```

- [ ] **Step 2: Verificación manual**

Desde la raíz del proyecto, con el `.env` apuntando a una base con al menos un usuario con contratos:

```bash
python -c "
from app.services.certificacion_service import CertificacionService
s = CertificacionService()
print('periodo_certificable:', s.periodo_certificable())
print('leyenda actual:', s.leyenda_periodo(*s.periodo_certificable()))
print('leyenda pasada:', s.leyenda_periodo(2024, 1))
periodos = s.periodos_disponibles_global()
print('rango global (primeros 3):', periodos[:3], '... total:', len(periodos))
"
```

Verifica que: `leyenda_periodo` del período actual no diga "gestión retroactiva"; `leyenda_periodo(2024, 1)` sí diga "Período pasado — Enero 2024 (gestión retroactiva)"; `periodos_disponibles_global()` empiece exactamente en el mismo `(año, mes)` que `periodo_certificable()` y no contenga ningún período futuro.

- [ ] **Step 3: Commit**

```bash
git add app/services/certificacion_service.py
git commit -m "feat(certificaciones): agrega helpers de rango de periodos y leyenda unificada"
```

---

### Task 2: Parametrizar año/mes en las funciones de generación de formatos

**Files:**
- Modify: `app/services/certificacion_service.py:102-308` (las 8 funciones de generación + `obtener_certificacion_periodo_actual`)

**Interfaces:**
- Consumes: nada nuevo de Task 1 (estos métodos no usan los helpers todavía; los helpers de Task 1 se consumen desde la UI en Task 4/5).
- Produces: las 8 funciones y `obtener_certificacion_periodo_actual` ahora aceptan `año: int = None, mes: int = None` al final de su firma — usados por Task 4 (llamadas desde `6_certificaciones.py`).

- [ ] **Step 1: `obtener_certificacion_periodo_actual`**

Reemplaza (línea 102-105):

```python
    def obtener_certificacion_periodo_actual(self, usuario_id: str, tipo_formato: str = None) -> Optional[Dict]:
        """Devuelve la certificación del período certificable hoy (mes actual o anterior)."""
        año, mes = self.periodo_certificable()
        return self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, tipo_formato)
```

por:

```python
    def obtener_certificacion_periodo_actual(
        self, usuario_id: str, tipo_formato: str = None, año: int = None, mes: int = None
    ) -> Optional[Dict]:
        """Devuelve la certificación del período dado (por defecto, el período
        certificable hoy: mes actual o anterior)."""
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        return self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, tipo_formato)
```

- [ ] **Step 2: `firmar_y_generar_dependencia`**

Cambia la línea 107-108 de:

```python
    def firmar_y_generar_dependencia(self, usuario_id: str, nombre_usuario: str) -> bool:
        año, mes = self.periodo_certificable()
```

a:

```python
    def firmar_y_generar_dependencia(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
```

- [ ] **Step 3: `firmar_y_generar_cuenta_cobro`**

Cambia la línea 138-139 de:

```python
    def firmar_y_generar_cuenta_cobro(self, usuario_id: str, nombre_usuario: str) -> bool:
        año, mes = self.periodo_certificable()
```

a:

```python
    def firmar_y_generar_cuenta_cobro(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
```

- [ ] **Step 4: `firmar_y_generar_retencion_primera`**

Cambia la línea 171-172 de:

```python
    def firmar_y_generar_retencion_primera(self, usuario_id: str, nombre_usuario: str) -> bool:
        año, mes = self.periodo_certificable()
```

a:

```python
    def firmar_y_generar_retencion_primera(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
```

- [ ] **Step 5: `firmar_y_generar_retencion_segunda`**

Cambia la línea 204-205 de:

```python
    def firmar_y_generar_retencion_segunda(self, usuario_id: str, nombre_usuario: str) -> bool:
        año, mes = self.periodo_certificable()
```

a:

```python
    def firmar_y_generar_retencion_segunda(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
```

- [ ] **Step 6: `firmar_y_generar_acta_compromiso`**

Cambia la línea 237-238 de:

```python
    def firmar_y_generar_acta_compromiso(self, usuario_id: str, nombre_usuario: str) -> bool:
        año, mes = self.periodo_certificable()
```

a:

```python
    def firmar_y_generar_acta_compromiso(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
```

- [ ] **Step 7: `firmar_y_generar_acta_recibo_entrega`**

Cambia la línea 258-264 de:

```python
    def firmar_y_generar_acta_recibo_entrega(self, usuario_id: str, nombre_usuario: str) -> bool:
        from app.services.usuario_service import UsuarioService
        req_bg = UsuarioService().validar_datos_balance_general_cps(usuario_id)
        if not req_bg["valido"]:
            raise ValueError(f"Faltan requisitos para generar el Balance General CPS: {', '.join(req_bg['faltantes'])}")

        año, mes = self.periodo_certificable()
```

a:

```python
    def firmar_y_generar_acta_recibo_entrega(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        from app.services.usuario_service import UsuarioService
        req_bg = UsuarioService().validar_datos_balance_general_cps(usuario_id)
        if not req_bg["valido"]:
            raise ValueError(f"Faltan requisitos para generar el Balance General CPS: {', '.join(req_bg['faltantes'])}")

        if año is None or mes is None:
            año, mes = self.periodo_certificable()
```

- [ ] **Step 8: `firmar_y_generar_acta_recibo_entrega_cps_real`**

Cambia la línea 284-290 de:

```python
    def firmar_y_generar_acta_recibo_entrega_cps_real(self, usuario_id: str, nombre_usuario: str) -> bool:
        from app.services.usuario_service import UsuarioService
        req_acta = UsuarioService().validar_datos_acta_recibo_entrega_cps(usuario_id)
        if not req_acta["valido"]:
            raise ValueError(f"Faltan requisitos para generar el Acta de Recibo y Entrega CPS: {', '.join(req_acta['faltantes'])}")

        año, mes = self.periodo_certificable()
```

a:

```python
    def firmar_y_generar_acta_recibo_entrega_cps_real(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        from app.services.usuario_service import UsuarioService
        req_acta = UsuarioService().validar_datos_acta_recibo_entrega_cps(usuario_id)
        if not req_acta["valido"]:
            raise ValueError(f"Faltan requisitos para generar el Acta de Recibo y Entrega CPS: {', '.join(req_acta['faltantes'])}")

        if año is None or mes is None:
            año, mes = self.periodo_certificable()
```

- [ ] **Step 9: Verificación manual**

```bash
python -c "
from app.services.certificacion_service import CertificacionService
s = CertificacionService()
print(s.obtener_certificacion_periodo_actual('000000000000000000000000'))
print(s.obtener_certificacion_periodo_actual('000000000000000000000000', año=2024, mes=1))
"
```

Ambas llamadas deben ejecutarse sin `TypeError` (el ObjectId falso simplemente no encuentra nada y devuelve `None`). Luego ejecuta `streamlit run app/main.py`, entra como un contratista real a "Formatos de contrato" y genera/descarga uno de los 4 formatos de autofirma (ej. Cuenta de cobro) — debe comportarse exactamente igual que antes de este cambio (todavía no está conectado el selector, esto solo confirma que no rompiste la firma por defecto).

- [ ] **Step 10: Commit**

```bash
git add app/services/certificacion_service.py
git commit -m "feat(certificaciones): permite pasar año/mes explicito a las funciones de generacion de formatos"
```

---

### Task 3: Parametrizar firma de supervisor y corregir el bug de auto-certificación retroactiva

**Files:**
- Modify: `app/services/certificacion_service.py:321-361` (`obtener_empleados_para_certificar`)
- Modify: `app/services/certificacion_service.py:425-475` (`registrar_firma`, `_intentar_auto_certificar`, `revocar_firma`)
- Modify: `app/services/certificacion_service.py:561-643` (`recuperar_auto_cert`, `certificar_empleado`)

**Interfaces:**
- Consumes: `_contrato_relevante(contratos, año, mes)` de Task 1.
- Produces: `obtener_empleados_para_certificar(tipo_formato=None, año=None, mes=None)`, `registrar_firma(..., año=None, mes=None)`, `revocar_firma(empleado_id, tipo, año=None, mes=None)`, `certificar_empleado(..., año=None, mes=None)` — usados por Task 5 (`admin_firmantes.py`).

**Importante — bug a corregir:** hoy `_intentar_auto_certificar` recibe `año`/`mes` del llamador pero al certificar llama a `self.certificar_empleado(...)` **sin pasarlos**, y `certificar_empleado` recalcula `self.periodo_certificable()` por su cuenta (línea 605). Es inofensivo hoy porque `año`/`mes` siempre coinciden con `periodo_certificable()` (nunca hay otra fuente). En cuanto `registrar_firma` reciba un período pasado explícito, este bug certificaría el mes de **hoy** en vez del mes que realmente se firmó. Este task lo corrige.

- [ ] **Step 1: `obtener_empleados_para_certificar` — parametrizar y usar `_contrato_relevante`**

Reemplaza (línea 321-328):

```python
    def obtener_empleados_para_certificar(self, tipo_formato: str = None) -> List[Dict]:
        """Lista todos los colaboradores con correspondencia, estado de firmas y contrato activo."""
        from app.services.correspondencia_service import CorrespondenciaService
        from app.repositories.usuario_repo import UsuarioRepositorio

        corr_service = CorrespondenciaService()
        usuario_repo = UsuarioRepositorio()
        año, mes = self.periodo_certificable()
```

por:

```python
    def obtener_empleados_para_certificar(
        self, tipo_formato: str = None, año: int = None, mes: int = None
    ) -> List[Dict]:
        """Lista todos los colaboradores con correspondencia, estado de firmas y contrato
        (vigente hoy si es el período actual, o vigente en ese mes si es un período pasado)."""
        from app.services.correspondencia_service import CorrespondenciaService
        from app.repositories.usuario_repo import UsuarioRepositorio

        corr_service = CorrespondenciaService()
        usuario_repo = UsuarioRepositorio()
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
```

Y reemplaza (línea 344-346):

```python
            contratos = usuario_data.get("contratos") or []
            contrato = self._contrato_vigente(contratos)
            tiene_contrato = bool(contrato.get("numero"))
```

por:

```python
            contratos = usuario_data.get("contratos") or []
            contrato = self._contrato_relevante(contratos, año, mes)
            tiene_contrato = bool(contrato.get("numero"))
```

- [ ] **Step 2: `registrar_firma` y `revocar_firma` — parametrizar**

Reemplaza (línea 425-443):

```python
    def registrar_firma(
        self,
        empleado_id: str,
        empleado_nombre: str,
        tipo: str,
        firmante_id: str,
        firmante_nombre: str,
        comentario: str | None = None,
    ) -> bool:
        """Registra la aprobación del firmante. Si con esta firma se completan
        las 3 y el contratista cumple requisitos, se certifica automáticamente."""
        año, mes = self.periodo_certificable()
        self.repo.registrar_firma(
            empleado_id, empleado_nombre, año, mes, tipo, firmante_id, firmante_nombre, comentario
        )
        self._intentar_auto_certificar(
            empleado_id, empleado_nombre, firmante_id, firmante_nombre, año, mes
        )
        return True
```

por:

```python
    def registrar_firma(
        self,
        empleado_id: str,
        empleado_nombre: str,
        tipo: str,
        firmante_id: str,
        firmante_nombre: str,
        comentario: str | None = None,
        año: int | None = None,
        mes: int | None = None,
    ) -> bool:
        """Registra la aprobación del firmante para el período dado (por defecto, el
        período certificable actual). Si con esta firma se completan las 3 y el
        contratista cumple requisitos, se certifica automáticamente para ESE período."""
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        self.repo.registrar_firma(
            empleado_id, empleado_nombre, año, mes, tipo, firmante_id, firmante_nombre, comentario
        )
        self._intentar_auto_certificar(
            empleado_id, empleado_nombre, firmante_id, firmante_nombre, año, mes
        )
        return True
```

Reemplaza (línea 472-475):

```python
    def revocar_firma(self, empleado_id: str, tipo: str) -> bool:
        """Revoca una firma previamente registrada."""
        año, mes = self.periodo_certificable()
        return self.repo.revocar_firma(empleado_id, año, mes, tipo)
```

por:

```python
    def revocar_firma(
        self, empleado_id: str, tipo: str, año: int | None = None, mes: int | None = None
    ) -> bool:
        """Revoca una firma previamente registrada del período dado (por defecto, el
        período certificable actual)."""
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        return self.repo.revocar_firma(empleado_id, año, mes, tipo)
```

- [ ] **Step 3: Corregir el bug de `certificar_empleado`/`_intentar_auto_certificar`/`recuperar_auto_cert`**

Reemplaza (línea 445-470):

```python
    def _intentar_auto_certificar(
        self,
        empleado_id: str,
        empleado_nombre: str,
        firmante_id: str,
        firmante_nombre: str,
        año: int,
        mes: int,
    ) -> None:
        """Auto-certifica cuando hay 3 firmas + contrato activo (sin importar estado de correspondencia)."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        cert = self.repo.buscar_por_usuario_periodo(empleado_id, año, mes)
        if not cert or cert.get("estado") == "aprobado":
            return

        firmas = cert.get("firmas", {})
        if not all(firmas.get(t) for t in ("corr", "gd", "secop")):
            return

        usuario = UsuarioRepositorio().buscar_por_id(empleado_id)
        contratos = (usuario.get("contratos") or []) if usuario else []
        if not self._contrato_vigente(contratos).get("numero"):
            return

        self.certificar_empleado(empleado_id, empleado_nombre, firmante_id, firmante_nombre)
```

por:

```python
    def _intentar_auto_certificar(
        self,
        empleado_id: str,
        empleado_nombre: str,
        firmante_id: str,
        firmante_nombre: str,
        año: int,
        mes: int,
    ) -> None:
        """Auto-certifica cuando hay 3 firmas + contrato vigente en ESE período
        (sin importar estado de correspondencia)."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        cert = self.repo.buscar_por_usuario_periodo(empleado_id, año, mes)
        if not cert or cert.get("estado") == "aprobado":
            return

        firmas = cert.get("firmas", {})
        if not all(firmas.get(t) for t in ("corr", "gd", "secop")):
            return

        usuario = UsuarioRepositorio().buscar_por_id(empleado_id)
        contratos = (usuario.get("contratos") or []) if usuario else []
        if not self._contrato_relevante(contratos, año, mes).get("numero"):
            return

        self.certificar_empleado(empleado_id, empleado_nombre, firmante_id, firmante_nombre, año=año, mes=mes)
```

(Nota: se usa `_contrato_relevante` en vez de `_contrato_vigente` para que la auto-certificación de un período pasado valide el contrato vigente en ESE mes, no el de hoy — consistente con Step 1.)

Reemplaza (línea 561-588, `recuperar_auto_cert`):

```python
    def recuperar_auto_cert(self, empleado_id: str, cert: dict) -> bool:
        """Certifica retroactivamente si el cert ya tiene las 3 firmas + contrato activo
        pero quedó en 'pendiente' por un fallo anterior en _intentar_auto_certificar.
        Retorna True si se certificó ahora."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        if not cert or cert.get("estado") == "aprobado":
            return False

        firmas = cert.get("firmas", {})
        if not all(firmas.get(t) for t in ("corr", "gd", "secop")):
            return False

        usuario = UsuarioRepositorio().buscar_por_id(empleado_id)
        contratos = (usuario.get("contratos") or []) if usuario else []
        if not self._contrato_vigente(contratos).get("numero"):
            return False

        # Usar la última firma como firmante registrado en el certificado
        ultima_firma = next(
            (firmas[t] for t in ("secop", "gd", "corr") if firmas.get(t)), None
        )
        firmante_id = str(ultima_firma.get("firmante_id", "")) if ultima_firma else ""
        firmante_nombre = ultima_firma.get("firmante_nombre", "") if ultima_firma else ""
        nombre_empleado = cert.get("nombre_usuario", "")

        self.certificar_empleado(empleado_id, nombre_empleado, firmante_id, firmante_nombre)
        return True
```

por:

```python
    def recuperar_auto_cert(self, empleado_id: str, cert: dict) -> bool:
        """Certifica retroactivamente si el cert ya tiene las 3 firmas + contrato vigente
        en su propio período pero quedó en 'pendiente' por un fallo anterior en
        _intentar_auto_certificar. Retorna True si se certificó ahora."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        if not cert or cert.get("estado") == "aprobado":
            return False

        firmas = cert.get("firmas", {})
        if not all(firmas.get(t) for t in ("corr", "gd", "secop")):
            return False

        año_cert = cert.get("año")
        mes_cert = cert.get("mes")

        usuario = UsuarioRepositorio().buscar_por_id(empleado_id)
        contratos = (usuario.get("contratos") or []) if usuario else []
        if not self._contrato_relevante(contratos, año_cert, mes_cert).get("numero"):
            return False

        # Usar la última firma como firmante registrado en el certificado
        ultima_firma = next(
            (firmas[t] for t in ("secop", "gd", "corr") if firmas.get(t)), None
        )
        firmante_id = str(ultima_firma.get("firmante_id", "")) if ultima_firma else ""
        firmante_nombre = ultima_firma.get("firmante_nombre", "") if ultima_firma else ""
        nombre_empleado = cert.get("nombre_usuario", "")

        self.certificar_empleado(
            empleado_id, nombre_empleado, firmante_id, firmante_nombre, año=año_cert, mes=mes_cert
        )
        return True
```

Reemplaza (línea 594-608, firma de `certificar_empleado`):

```python
    def certificar_empleado(
        self,
        usuario_id_empleado: str,
        nombre_empleado: str,
        supervisor_id: str,
        supervisor_nombre: str,
        observaciones: str = "",
    ) -> bool:
        """Certifica al colaborador para el período actual.
        Si ya existe un hash previo, lo preserva para que los PDFs ya entregados
        sigan siendo verificables con el código original."""
        año, mes = self.periodo_certificable()
        ahora_utc = datetime.now(timezone.utc)
```

por:

```python
    def certificar_empleado(
        self,
        usuario_id_empleado: str,
        nombre_empleado: str,
        supervisor_id: str,
        supervisor_nombre: str,
        observaciones: str = "",
        año: int = None,
        mes: int = None,
    ) -> bool:
        """Certifica al colaborador para el período dado (por defecto, el período
        certificable actual).
        Si ya existe un hash previo, lo preserva para que los PDFs ya entregados
        sigan siendo verificables con el código original."""
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        ahora_utc = datetime.now(timezone.utc)
```

- [ ] **Step 4: Verificación manual — regresión del flujo actual**

Ejecuta `streamlit run app/main.py`. Como supervisor con permiso `certificacion.firmar_corr` (o `gd`/`secop`), entra a "Sup. Formatos" y aprueba la firma de un contratista para el período actual (todavía sin selector conectado — este task no lo agrega, solo prepara el service). Si el contratista ya tenía las otras 2 firmas y contrato vigente, confirma que la auto-certificación sigue disparando igual que antes (el certificado pasa a "aprobado" y genera hash). Esto confirma que la corrección del bug no rompió el camino feliz de hoy.

También confirma que `app/pages_admin/admin_certificaciones.py` sigue funcionando sin cambios: entra a "Seguimiento - Formatos" y verifica que la lista de empleados y sus contratos se vean igual que antes (esta página sigue llamando `obtener_empleados_para_certificar()` sin argumentos, que ahora usa `_contrato_relevante` pero para el período actual eso es idéntico a `_contrato_vigente`).

- [ ] **Step 5: Commit**

```bash
git add app/services/certificacion_service.py
git commit -m "fix(certificaciones): permite periodo explicito en firma/revocacion y corrige auto-cert para periodos retroactivos"
```

---

### Task 4: UI del contratista — selector de período en "Formatos de contrato"

**Files:**
- Modify: `app/pages/6_certificaciones.py`

**Interfaces:**
- Consumes: `servicio.periodos_disponibles_usuario(usuario_id)`, `servicio.leyenda_periodo(año, mes)`, `servicio._contrato_relevante(contratos, año, mes)` de Task 1; los parámetros `año=`, `mes=` opcionales de Task 2 en `obtener_certificacion_periodo_actual` y las 7 `firmar_y_generar_*`.

- [ ] **Step 1: Agregar el selector en `render()` y quitar `es_anterior`**

Reemplaza (línea 1167-1169):

```python
    año_cert, mes_cert = servicio.periodo_certificable()
    nombre_mes_cert = MESES_ES[mes_cert - 1]
    es_anterior = servicio.es_mes_anterior()
```

por:

```python
    periodos_usuario = servicio.periodos_disponibles_usuario(usuario_id)
    año_cert, mes_cert = st.selectbox(
        "📅 Período de trabajo",
        options=periodos_usuario,
        format_func=lambda p: f"{MESES_ES[p[1] - 1]} {p[0]}",
        index=0,
        key="cert_periodo_seleccionado",
    )
    nombre_mes_cert = MESES_ES[mes_cert - 1]
```

- [ ] **Step 2: Actualizar las 8 llamadas a `_render_opcion_*` en `render()` (quitar `es_anterior`)**

Reemplaza el bloque (línea 1295-1318):

```python
    with col_contenido:
        tab_activa = st.session_state.get("tab_formato_activo")
        if tab_activa == 1:
            _render_opcion_1_cuenta_cobro(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado)
        elif tab_activa == 2:
            _render_opcion_2_retencion_primera(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado)
        elif tab_activa == 3:
            _render_opcion_3_retencion_segunda(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado)
        elif tab_activa == 4:
            _render_opcion_4_declarante_dependencia(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado)
        elif tab_activa == 5:
            _render_opcion_5_acta_compromiso(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado)
        elif tab_activa == 6:
            _render_opcion_6_gestion_corr(servicio, usuario_id, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado)
        elif tab_activa == 7:
            _render_opcion_7_herramientas()
        elif tab_activa == 8:
            _render_opcion_8_acta_recibo_entrega(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado)
        elif tab_activa == 9:
            _render_opcion_9_acta_recibo_entrega_real(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado)
        elif tab_activa == 10:
            _render_opcion_8_historial(servicio, usuario_id, año_cert, mes_cert, bloqueado)
        elif tab_activa == 11:
            _render_verificador_codigo(servicio)
        else:
            st.info("👈 Selecciona un formato en el menú de la izquierda para visualizar su contenido.")
```

por:

```python
    with col_contenido:
        tab_activa = st.session_state.get("tab_formato_activo")
        if tab_activa == 1:
            _render_opcion_1_cuenta_cobro(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 2:
            _render_opcion_2_retencion_primera(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 3:
            _render_opcion_3_retencion_segunda(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 4:
            _render_opcion_4_declarante_dependencia(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 5:
            _render_opcion_5_acta_compromiso(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 6:
            _render_opcion_6_gestion_corr(servicio, usuario_id, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 7:
            _render_opcion_7_herramientas()
        elif tab_activa == 8:
            _render_opcion_8_acta_recibo_entrega(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 9:
            _render_opcion_9_acta_recibo_entrega_real(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 10:
            _render_opcion_8_historial(servicio, usuario_id, año_cert, mes_cert, bloqueado)
        elif tab_activa == 11:
            _render_verificador_codigo(servicio)
        else:
            st.info("👈 Selecciona un formato en el menú de la izquierda para visualizar su contenido.")
```

- [ ] **Step 3: `_render_opcion_6_gestion_corr` — leyenda, período en llamadas de servicio, y `_mostrar_avance`**

Reemplaza (línea 212-230):

```python
def _render_opcion_6_gestion_corr(servicio, usuario_id, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado=False):
    mostrar_titulo_decorado("Formato de control a la correspondencia - Gestión documental - SECOP II")

    if bloqueado:
        _aviso_bloqueado()
        return

    etiqueta = (
        f"Período anterior — {nombre_mes_cert} {año_cert} (ponerse al día)"
        if es_anterior
        else f"Período actual — {nombre_mes_cert} {año_cert}"
    )
    st.subheader(etiqueta)

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id)

    if cert_actual and cert_actual.get("estado") != "aprobado":
        if servicio.recuperar_auto_cert(usuario_id, cert_actual):
            cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id)
```

por:

```python
def _render_opcion_6_gestion_corr(servicio, usuario_id, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    mostrar_titulo_decorado("Formato de control a la correspondencia - Gestión documental - SECOP II")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, año=año_cert, mes=mes_cert)

    if cert_actual and cert_actual.get("estado") != "aprobado":
        if servicio.recuperar_auto_cert(usuario_id, cert_actual):
            cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, año=año_cert, mes=mes_cert)
```

Más abajo en la misma función, reemplaza (línea 271-273):

```python
    else:
        st.warning(f"Tu certificado de **{nombre_mes_cert} {año_cert}** aún está en proceso.")
        _mostrar_avance(usuario_id, cert_actual)
```

por:

```python
    else:
        st.warning(f"Tu certificado de **{nombre_mes_cert} {año_cert}** aún está en proceso.")
        _mostrar_avance(servicio, usuario_id, año_cert, mes_cert, cert_actual)
```

- [ ] **Step 4: `_mostrar_avance` — recibir servicio/período y usar `_contrato_relevante`**

Reemplaza (línea 112-120):

```python
def _mostrar_avance(usuario_id: str, cert_actual) -> None:
    from app.repositories.usuario_repo import UsuarioRepositorio

    firmas = cert_actual.get("firmas", {}) if cert_actual else {}

    usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
    contratos = usuario_data.get("contratos") or []
    contrato = CertificacionService._contrato_vigente(contratos)
    tiene_contrato = bool(contrato.get("numero"))
```

por:

```python
def _mostrar_avance(servicio: CertificacionService, usuario_id: str, año: int, mes: int, cert_actual) -> None:
    from app.repositories.usuario_repo import UsuarioRepositorio

    firmas = cert_actual.get("firmas", {}) if cert_actual else {}

    usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
    contratos = usuario_data.get("contratos") or []
    contrato = servicio._contrato_relevante(contratos, año, mes)
    tiene_contrato = bool(contrato.get("numero"))
```

- [ ] **Step 5: `_render_opcion_1_cuenta_cobro`**

Reemplaza (línea 470-486):

```python
def _render_opcion_1_cuenta_cobro(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Cuenta de Cobro")

    if bloqueado:
        _aviso_bloqueado()
        return

    etiqueta = (
        f"Período anterior — {nombre_mes_cert} {año_cert} (ponerse al día)"
        if es_anterior
        else f"Período actual — {nombre_mes_cert} {año_cert}"
    )
    st.subheader(etiqueta)

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "cuenta_cobro")
```

por:

```python
def _render_opcion_1_cuenta_cobro(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Cuenta de Cobro")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "cuenta_cobro", año=año_cert, mes=mes_cert)
```

Más abajo en la misma función, reemplaza (línea 530-531):

```python
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_vigente(contratos)
```

por:

```python
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)
```

Y reemplaza (línea 558-559):

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_cuenta_cobro(usuario_id, nombre_usuario_actual):
```

por:

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_cuenta_cobro(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
```

- [ ] **Step 6: `_render_opcion_2_retencion_primera`**

Reemplaza (línea 564-580):

```python
def _render_opcion_2_retencion_primera(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Disminución Base Retención en la Fuente Contrato - Primera Cuenta")

    if bloqueado:
        _aviso_bloqueado()
        return

    etiqueta = (
        f"Período anterior — {nombre_mes_cert} {año_cert} (ponerse al día)"
        if es_anterior
        else f"Período actual — {nombre_mes_cert} {año_cert}"
    )
    st.subheader(etiqueta)

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "retencion_fuente_primera")
```

por:

```python
def _render_opcion_2_retencion_primera(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Disminución Base Retención en la Fuente Contrato - Primera Cuenta")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "retencion_fuente_primera", año=año_cert, mes=mes_cert)
```

Más abajo, reemplaza (línea 625-626):

```python
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_vigente(contratos)
```

por:

```python
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)
```

Y reemplaza (línea 656-657):

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_retencion_primera(usuario_id, nombre_usuario_actual):
```

por:

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_retencion_primera(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
```

- [ ] **Step 7: `_render_opcion_3_retencion_segunda`**

Reemplaza (línea 662-678):

```python
def _render_opcion_3_retencion_segunda(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Disminución Base Retención en la Fuente Contrato - Segunda Cuenta ++")

    if bloqueado:
        _aviso_bloqueado()
        return

    etiqueta = (
        f"Período anterior — {nombre_mes_cert} {año_cert} (ponerse al día)"
        if es_anterior
        else f"Período actual — {nombre_mes_cert} {año_cert}"
    )
    st.subheader(etiqueta)

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "retencion_fuente_segunda")
```

por:

```python
def _render_opcion_3_retencion_segunda(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Disminución Base Retención en la Fuente Contrato - Segunda Cuenta ++")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "retencion_fuente_segunda", año=año_cert, mes=mes_cert)
```

Más abajo, reemplaza (línea 723-724):

```python
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_vigente(contratos)
```

por:

```python
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)
```

Y reemplaza (línea 754-755):

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_retencion_segunda(usuario_id, nombre_usuario_actual):
```

por:

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_retencion_segunda(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
```

- [ ] **Step 8: `_render_opcion_4_declarante_dependencia`**

Reemplaza (línea 760-776):

```python
def _render_opcion_4_declarante_dependencia(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Condición de Declarante y Existencia y Dependencia Económica")

    if bloqueado:
        _aviso_bloqueado()
        return

    etiqueta = (
        f"Período anterior — {nombre_mes_cert} {año_cert} (ponerse al día)"
        if es_anterior
        else f"Período actual — {nombre_mes_cert} {año_cert}"
    )
    st.subheader(etiqueta)

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "dependencia_economica")
```

por:

```python
def _render_opcion_4_declarante_dependencia(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Condición de Declarante y Existencia y Dependencia Económica")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "dependencia_economica", año=año_cert, mes=mes_cert)
```

Más abajo, reemplaza (línea 821-823):

```python
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_vigente(contratos)
```

por:

```python
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)
```

Y reemplaza (línea 851-852):

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_dependencia(usuario_id, nombre_usuario_actual):
```

por:

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_dependencia(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
```

- [ ] **Step 9: `_render_opcion_5_acta_compromiso`**

Reemplaza (línea 857-873):

```python
def _render_opcion_5_acta_compromiso(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Acta de Compromiso")

    if bloqueado:
        _aviso_bloqueado()
        return

    etiqueta = (
        f"Período anterior — {nombre_mes_cert} {año_cert} (ponerse al día)"
        if es_anterior
        else f"Período actual — {nombre_mes_cert} {año_cert}"
    )
    st.subheader(etiqueta)

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "acta_compromiso")
```

por:

```python
def _render_opcion_5_acta_compromiso(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Acta de Compromiso")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "acta_compromiso", año=año_cert, mes=mes_cert)
```

Más abajo, reemplaza (línea 910-912):

```python
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_vigente(contratos)
```

por:

```python
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)
```

Y reemplaza (línea 953-954):

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_acta_compromiso(usuario_id, nombre_usuario_actual):
```

por:

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_acta_compromiso(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
```

- [ ] **Step 10: `_render_opcion_9_acta_recibo_entrega_real`**

Reemplaza (línea 959-975):

```python
def _render_opcion_9_acta_recibo_entrega_real(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Acta de recibo y entrega CPS")

    if bloqueado:
        _aviso_bloqueado()
        return

    etiqueta = (
        f"Período anterior — {nombre_mes_cert} {año_cert} (ponerse al día)"
        if es_anterior
        else f"Período actual — {nombre_mes_cert} {año_cert}"
    )
    st.subheader(etiqueta)

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "acta_recibo_entrega_cps_real")
```

por:

```python
def _render_opcion_9_acta_recibo_entrega_real(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Acta de recibo y entrega CPS")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "acta_recibo_entrega_cps_real", año=año_cert, mes=mes_cert)
```

Más abajo, reemplaza (línea 1023-1025):

```python
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_vigente(contratos)
```

por:

```python
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)
```

Y reemplaza (línea 1039-1040):

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_acta_recibo_entrega_cps_real(usuario_id, nombre_usuario_actual):
```

por:

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_acta_recibo_entrega_cps_real(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
```

- [ ] **Step 11: `_render_opcion_8_acta_recibo_entrega`**

Reemplaza (línea 1045-1061):

```python
def _render_opcion_8_acta_recibo_entrega(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, es_anterior, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Balance General CPS")

    if bloqueado:
        _aviso_bloqueado()
        return

    etiqueta = (
        f"Período anterior — {nombre_mes_cert} {año_cert} (ponerse al día)"
        if es_anterior
        else f"Período actual — {nombre_mes_cert} {año_cert}"
    )
    st.subheader(etiqueta)

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "acta_recibo_entrega_cps")
```

por:

```python
def _render_opcion_8_acta_recibo_entrega(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Balance General CPS")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "acta_recibo_entrega_cps", año=año_cert, mes=mes_cert)
```

Más abajo, reemplaza (línea 1109-1111):

```python
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_vigente(contratos)
```

por:

```python
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)
```

Y reemplaza (línea 1125-1126):

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_acta_recibo_entrega(usuario_id, nombre_usuario_actual):
```

por:

```python
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_acta_recibo_entrega(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
```

- [ ] **Step 12: Verificación manual completa**

Ejecuta `streamlit run app/main.py` y entra como un contratista con al menos 2-3 meses de contrato activo (para tener varias opciones en el selector):

1. Con el selector en su valor por defecto (el primero de la lista), genera y descarga cada uno de los 8 formatos → debe verse y comportarse exactamente igual que antes de este plan.
2. Cambia el selector a un mes pasado en el que **nunca** generaste ningún formato. Entra a "Cuenta de cobro" → debe mostrar "Aún no has generado el formato para el período {ese mes}" con el botón "Firmar y Generar Formato" habilitado si tenías contrato vigente ese mes (revisa el campo "Contrato" mostrado — debe corresponder al contrato de esa época, no al actual si ya cambiaste de contrato). Genera el formato y confirma que se descarga con los datos correctos de esa época.
3. Vuelve a "Historial de formatos" → el formato recién generado del mes pasado debe aparecer en la lista.
4. Cambia el selector a un mes en el que el sistema está en la ventana de "ponerse al día" (si aplica hoy) → el subtítulo debe decir "Período anterior — ... (ponerse al día, disponible hasta el día X...)". Cambia a cualquier otro mes más antiguo → debe decir "Período pasado — ... (gestión retroactiva)".
5. Si tienes un usuario sin ningún contrato registrado, confirma que el selector solo muestra una opción (el período certificable actual).

- [ ] **Step 13: Commit**

```bash
git add app/pages/6_certificaciones.py
git commit -m "feat(certificaciones): agrega selector de periodo retroactivo en Formatos de contrato"
```

---

### Task 5: UI del supervisor — selector de período en "Sup. Formatos"

**Files:**
- Modify: `app/pages_admin/admin_firmantes.py`

**Interfaces:**
- Consumes: `servicio.periodos_disponibles_global()`, `servicio.leyenda_periodo(año, mes)` de Task 1; `obtener_empleados_para_certificar(año=, mes=)`, `registrar_firma(..., año=, mes=)`, `revocar_firma(..., año=, mes=)` de Task 3.

- [ ] **Step 1: Agregar el selector y la leyenda en `render()`**

Reemplaza (línea 519-550):

```python
    año, mes = servicio.periodo_certificable()
    nombre_mes = MESES_ES[mes - 1]
    es_anterior = servicio.es_mes_anterior()

    # Inyectar CSS para dar fondo verde al botón de certificado
    st.markdown(
        """
        <style>
        div[data-testid="stDownloadButton"] button {
            background-color: #2e7d32 !important;
            color: white !important;
            border: 1px solid #1b5e20 !important;
        }
        div[data-testid="stDownloadButton"] button:hover {
            background-color: #1b5e20 !important;
            color: white !important;
            border-color: #1b5e20 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    mostrar_titulo_decorado("Sup. Formatos")
    st.caption(f"Período certificable: **{nombre_mes} {año}**")

    if es_anterior:
        _dia_cierre = servicio._dia_inicio_periodo() - 1
        st.warning(
            f"Estás aprobando el **mes anterior: {nombre_mes} {año}** "
            f"(ventana disponible hasta el día {_dia_cierre} del mes en curso)."
        )
```

por:

```python
    # Inyectar CSS para dar fondo verde al botón de certificado
    st.markdown(
        """
        <style>
        div[data-testid="stDownloadButton"] button {
            background-color: #2e7d32 !important;
            color: white !important;
            border: 1px solid #1b5e20 !important;
        }
        div[data-testid="stDownloadButton"] button:hover {
            background-color: #1b5e20 !important;
            color: white !important;
            border-color: #1b5e20 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    mostrar_titulo_decorado("Sup. Formatos")

    periodos_globales = servicio.periodos_disponibles_global()
    año, mes = st.selectbox(
        "📅 Período a firmar",
        options=periodos_globales,
        format_func=lambda p: f"{MESES_ES[p[1] - 1]} {p[0]}",
        index=0,
        key="sup_periodo_seleccionado",
    )
    nombre_mes = MESES_ES[mes - 1]
    st.caption(servicio.leyenda_periodo(año, mes))
```

- [ ] **Step 2: `obtener_empleados_para_certificar` — pasar el período seleccionado**

Reemplaza (línea 624-625):

```python
        with st.spinner("Consultando estado de correspondencia…"):
            empleados = servicio.obtener_empleados_para_certificar()
```

por:

```python
        with st.spinner("Consultando estado de correspondencia…"):
            empleados = servicio.obtener_empleados_para_certificar(año=año, mes=mes)
```

- [ ] **Step 3: `revocar_firma` — pasar el período seleccionado**

Reemplaza (línea 801-803):

```python
                                    help="Revocar mi aprobación.",
                                ):
                                    servicio.revocar_firma(uid, tipo_mi_firma)
                                    st.rerun()
```

por:

```python
                                    help="Revocar mi aprobación.",
                                ):
                                    servicio.revocar_firma(uid, tipo_mi_firma, año=año, mes=mes)
                                    st.rerun()
```

- [ ] **Step 4: `_dialog_confirmar_firma` — pasar el período al registrar la firma**

Reemplaza (línea 240-245):

```python
    with c1:
        if st.button("Confirmar aprobación", type="primary", use_container_width=True):
            firmante_nombre = sesion.get("nombre_completo") or sesion["usuario"]
            servicio.registrar_firma(uid, nombre, tipo, sesion["id"], firmante_nombre, comentario)
            st.session_state.pop("_confirmar_firma", None)
            st.rerun()
```

por:

```python
    with c1:
        if st.button("Confirmar aprobación", type="primary", use_container_width=True):
            firmante_nombre = sesion.get("nombre_completo") or sesion["usuario"]
            servicio.registrar_firma(uid, nombre, tipo, sesion["id"], firmante_nombre, comentario, año=año, mes=mes)
            st.session_state.pop("_confirmar_firma", None)
            st.rerun()
```

(`año`/`mes` ya llegan a `_dialog_confirmar_firma` como parámetros de la función — ver línea 191-192 — no se toca la firma de la función, solo el cuerpo.)

- [ ] **Step 5: `_render_panel_actas` — recibir y usar el período seleccionado**

Reemplaza (línea 252-289):

```python
def _render_panel_actas(servicio: CertificacionService, sesion: dict, tipo_formato: str) -> None:
    permisos = sesion.get("permisos", [])
    roles_sesion = sesion.get("roles", [])
    es_admin = any(r in {"admin", "administrador"} for r in roles_sesion)

    orden = ORDEN_FIRMAS_ACTAS[tipo_formato]
    mis_roles = [r for r in orden if _META_FIRMA_ACTAS[r][2] in permisos]

    if not es_admin and not mis_roles:
        st.warning("No tienes permiso de firma para este formato.")
        return

    st.subheader(_LABEL_FORMATO_ACTAS[tipo_formato])

    if len(mis_roles) > 1:
        opciones_rol = {r: _META_FIRMA_ACTAS[r][1] for r in mis_roles}
        rol_activo = st.radio(
            "Estás actuando como firmante de:",
            options=list(opciones_rol.keys()),
            format_func=lambda r: f"✍️ {opciones_rol[r]}",
            horizontal=True,
            key=f"sel_rol_actas_{tipo_formato}",
        )
    elif mis_roles:
        rol_activo = mis_roles[0]
    else:
        rol_activo = None

    if es_admin and rol_activo is None:
        st.info("🛡️ **Administrador** — Vista de solo lectura.")
    elif rol_activo:
        _, label_largo, _ = _META_FIRMA_ACTAS[rol_activo]
        st.info(f"✍️ **Actuando como:** Firma {label_largo}")

    st.divider()

    with st.spinner("Consultando colaboradores…"):
        empleados = servicio.obtener_empleados_para_certificar(tipo_formato=tipo_formato)
    empleados = [e for e in empleados if e.get("certificacion")]
```

por:

```python
def _render_panel_actas(
    servicio: CertificacionService, sesion: dict, tipo_formato: str, año: int, mes: int
) -> None:
    permisos = sesion.get("permisos", [])
    roles_sesion = sesion.get("roles", [])
    es_admin = any(r in {"admin", "administrador"} for r in roles_sesion)

    orden = ORDEN_FIRMAS_ACTAS[tipo_formato]
    mis_roles = [r for r in orden if _META_FIRMA_ACTAS[r][2] in permisos]

    if not es_admin and not mis_roles:
        st.warning("No tienes permiso de firma para este formato.")
        return

    st.subheader(_LABEL_FORMATO_ACTAS[tipo_formato])

    if len(mis_roles) > 1:
        opciones_rol = {r: _META_FIRMA_ACTAS[r][1] for r in mis_roles}
        rol_activo = st.radio(
            "Estás actuando como firmante de:",
            options=list(opciones_rol.keys()),
            format_func=lambda r: f"✍️ {opciones_rol[r]}",
            horizontal=True,
            key=f"sel_rol_actas_{tipo_formato}",
        )
    elif mis_roles:
        rol_activo = mis_roles[0]
    else:
        rol_activo = None

    if es_admin and rol_activo is None:
        st.info("🛡️ **Administrador** — Vista de solo lectura.")
    elif rol_activo:
        _, label_largo, _ = _META_FIRMA_ACTAS[rol_activo]
        st.info(f"✍️ **Actuando como:** Firma {label_largo}")

    st.divider()

    with st.spinner("Consultando colaboradores…"):
        empleados = servicio.obtener_empleados_para_certificar(tipo_formato=tipo_formato, año=año, mes=mes)
    empleados = [e for e in empleados if e.get("certificacion")]
```

- [ ] **Step 6: Actualizar la llamada a `_render_panel_actas`**

Reemplaza (línea 818-820):

```python
    tab_actas = st.session_state.get("tab_actas_activo")
    if tab_actas:
        _render_panel_actas(servicio, sesion, tab_actas)
```

por:

```python
    tab_actas = st.session_state.get("tab_actas_activo")
    if tab_actas:
        _render_panel_actas(servicio, sesion, tab_actas, año, mes)
```

- [ ] **Step 7: Verificación manual completa**

Ejecuta `streamlit run app/main.py` como supervisor con permisos de firma (idealmente uno con `certificacion.firmar_corr` y otro de rol de actas, o el mismo usuario con varios permisos):

1. Con el selector en su valor por defecto, aprueba/revoca una firma corr/gd/secop del período actual → debe comportarse exactamente igual que antes.
2. Cambia el selector a un mes pasado donde algún contratista tenga un formato "Gestión Corr-GD-SECOP" pendiente (generado previamente vía Task 4, Step 12.2, o uno ya existente en la base). Aprueba la firma que te falte → confirma que la firma se guarda en el documento de ESE mes (revisa en `mongosh`: `db.certificaciones.findOne({usuario_id: ObjectId("..."), año: <ese año>, mes: <ese mes>})` y que `firmas.<tu tipo>` tenga fecha de hoy) y que el período actual no se vio afectado.
3. Si con tu firma se completan las 3 (corr/gd/secop) y el contratista tenía contrato vigente en ese mes pasado, confirma que el documento de ESE período pasa a `estado: "aprobado"` con `hash_verificacion` — y que **no** se creó ni modificó accidentalmente un documento del período actual (`db.certificaciones.findOne({usuario_id: ObjectId("..."), año: <año actual>, mes: <mes actual>})` debe seguir igual que antes de la prueba). Esto confirma que el bug de Task 3 quedó corregido.
4. Cambia a la pestaña de una acta (ej. "2- Acta de compromiso") con el selector en un mes pasado donde un contratista tenga esa acta generada. Firma en orden (o revoca) y confirma que el stepper y la cascada de revocación siguen funcionando correctamente para ese documento específico.
5. Verifica que `app/pages_admin/admin_certificaciones.py` ("Seguimiento - Formatos") sigue mostrando el período actual sin ningún selector — no se tocó en este plan.

- [ ] **Step 8: Commit**

```bash
git add app/pages_admin/admin_firmantes.py
git commit -m "feat(certificaciones): agrega selector de periodo retroactivo en Sup. Formatos"
```
