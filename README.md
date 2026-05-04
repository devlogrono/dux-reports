# dux

## Ejecución Local
```bash
FLASK_APP=dux:create_app flask --debug run --port 5001  
```

## Migraciones de base de datos (Alembic)

El proyecto parte de la revisión **baseline_20250708**.  Todas las migraciones
futuras deben colgar de esta para mantener una historia lineal y evitar
conflictos.

Pasos recomendados:

1. Crea tu rama de trabajo y asegúrate de tener la base actualizada:

   ```bash
   git checkout -b feature/mi-cambio
   git pull origin main
   ```

2. Genera la migración con autogeneración de metadatos ya reflejados:

   ```bash
   alembic revision --autogenerate -m "<descripción>"
   ```

   *No uses* `--head` ni cambies `down_revision`; Alembic ajustará la cadena
   automáticamente al último commit de la rama principal de migraciones.

3. Revisa y ajusta el script generado antes de aplicarlo.

4. Aplica la migración localmente para verificar:

   ```bash
   alembic upgrade head
   ```

5. Sube la rama y abre un *pull-request*.  La CI aplicará `alembic upgrade head`
   contra una base de pruebas para asegurar su validez.

Resumiendo: **nunca reescribas migraciones ya compartidas**.  Si necesitas
corregir algo, genera una nueva migración que modifique lo necesario.