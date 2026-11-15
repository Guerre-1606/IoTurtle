-- IoTurtle · tablas para la base de datos nueva (TiDB Cloud)
-- Pega todo esto en el SQL Editor de TiDB y dale Run.

CREATE DATABASE IF NOT EXISTS ioturtle;
USE ioturtle;

CREATE TABLE IF NOT EXISTS usuarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  correo VARCHAR(190) NOT NULL UNIQUE,
  contrasena_hash VARCHAR(255) NULL,
  google_id VARCHAR(64) NULL UNIQUE,
  foto VARCHAR(500) NULL,
  rol ENUM('cuidador','biologo','veterinario','admin') NOT NULL DEFAULT 'cuidador',
  creado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS configuracion_usuario (
  usuario_id INT PRIMARY KEY,
  canal VARCHAR(20) NULL,
  canal_nombre VARCHAR(120) NULL,
  read_key VARCHAR(64) NULL,
  write_key VARCHAR(64) NULL,
  tmax DECIMAL(5,2) NOT NULL DEFAULT 30,
  tmin DECIMAL(5,2) NOT NULL DEFAULT 20,
  hmin DECIMAL(5,2) NOT NULL DEFAULT 60,
  actualizado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_config_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

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
  field8 TINYINT NULL,
  guardado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY canal_entry (canal, entry_id),
  INDEX canal_recibido (canal, recibido)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
