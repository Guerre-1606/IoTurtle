CREATE DATABASE IF NOT EXISTS ioturtle CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
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
);
