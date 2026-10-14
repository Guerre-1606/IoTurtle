-- IoTurtle · Migración: configuración por usuario
-- Ejecútalo UNA sola vez en phpMyAdmin, con tu base de datos seleccionada a la izquierda.

-- 1. Tabla con el canal, la clave y los límites de cada usuario
CREATE TABLE IF NOT EXISTS configuracion_usuario (
  usuario_id INT PRIMARY KEY,
  canal VARCHAR(20) NULL,
  canal_nombre VARCHAR(120) NULL,
  read_key VARCHAR(64) NULL,
  tmax DECIMAL(5,2) NOT NULL DEFAULT 30,
  tmin DECIMAL(5,2) NOT NULL DEFAULT 20,
  hmin DECIMAL(5,2) NOT NULL DEFAULT 60,
  actualizado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_config_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

-- 2. Cada lectura sabe de qué canal viene.
--    Las lecturas que ya tienes quedan asignadas al canal 3525448.
ALTER TABLE lecturas ADD COLUMN canal VARCHAR(20) NOT NULL DEFAULT '3525448' AFTER id;
ALTER TABLE lecturas ALTER COLUMN canal DROP DEFAULT;

-- 3. El entry_id ya no es único solo: se repite entre canales distintos.
ALTER TABLE lecturas DROP INDEX entry_id;
ALTER TABLE lecturas ADD UNIQUE KEY canal_entry (canal, entry_id);
ALTER TABLE lecturas ADD INDEX canal_recibido (canal, recibido);
