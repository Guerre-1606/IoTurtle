-- IoTurtle · Tablas de datos (instalación nueva)
-- Ejecútalo después de db.sql, con tu base de datos seleccionada.

CREATE TABLE IF NOT EXISTS lecturas (
  id INT AUTO_INCREMENT PRIMARY KEY,
  canal VARCHAR(20) NOT NULL,
  entry_id INT NOT NULL,
  recibido DATETIME NOT NULL,
  field1 DECIMAL(6,2) NULL,
  field2 DECIMAL(6,2) NULL,
  field3 DECIMAL(6,2) NULL,
  field4 DECIMAL(6,2) NULL,
  field5 DECIMAL(6,2) NULL,
  field6 DECIMAL(6,2) NULL,
  field7 DECIMAL(6,2) NULL,
  guardado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY canal_entry (canal, entry_id),
  INDEX canal_recibido (canal, recibido)
);

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
