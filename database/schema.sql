-- =====================================================
-- BLOOD COMPONENT INVENTORY AND EMERGENCY MATCHING SYSTEM
-- Database Schema
-- =====================================================

CREATE DATABASE IF NOT EXISTS blood_management_db;

USE blood_management_db;


-- =====================================================
-- 1. BLOOD GROUP
-- =====================================================

CREATE TABLE blood_group (
    blood_group_id INT AUTO_INCREMENT PRIMARY KEY,
    blood_group VARCHAR(5) NOT NULL UNIQUE
);


-- =====================================================
-- 2. BLOOD COMPONENT
-- =====================================================

CREATE TABLE blood_component (
    component_id INT AUTO_INCREMENT PRIMARY KEY,
    component_name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
);


-- =====================================================
-- 3. DONOR
-- =====================================================

CREATE TABLE donor (
    donor_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    gender VARCHAR(20),
    phone VARCHAR(15) NOT NULL UNIQUE,
    email VARCHAR(100) UNIQUE,
    address VARCHAR(255),
    blood_group_id INT NOT NULL,
    last_donation_date DATE,
    eligibility_status VARCHAR(20) DEFAULT 'Eligible',

    FOREIGN KEY (blood_group_id)
        REFERENCES blood_group(blood_group_id)
);


-- =====================================================
-- 4. DONATION
-- =====================================================

CREATE TABLE donation (
    donation_id INT AUTO_INCREMENT PRIMARY KEY,
    donor_id INT NOT NULL,
    donation_date DATE NOT NULL,
    component_id INT NOT NULL,
    quantity_ml INT NOT NULL,
    donation_status VARCHAR(30) DEFAULT 'Collected',

    FOREIGN KEY (donor_id)
        REFERENCES donor(donor_id),

    FOREIGN KEY (component_id)
        REFERENCES blood_component(component_id)
);


-- =====================================================
-- 5. STORAGE LOCATION
-- =====================================================

CREATE TABLE storage_location (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    location_name VARCHAR(100) NOT NULL,
    refrigerator_number VARCHAR(50),
    shelf_number VARCHAR(50)
);


-- =====================================================
-- 6. BLOOD UNIT
-- =====================================================

CREATE TABLE blood_unit (
    unit_id INT AUTO_INCREMENT PRIMARY KEY,
    donation_id INT NOT NULL,
    blood_group_id INT NOT NULL,
    component_id INT NOT NULL,
    collection_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    quantity_ml INT NOT NULL,
    location_id INT,
    status VARCHAR(30) DEFAULT 'Available',

    FOREIGN KEY (donation_id)
        REFERENCES donation(donation_id),

    FOREIGN KEY (blood_group_id)
        REFERENCES blood_group(blood_group_id),

    FOREIGN KEY (component_id)
        REFERENCES blood_component(component_id),

    FOREIGN KEY (location_id)
        REFERENCES storage_location(location_id)
);


-- =====================================================
-- 7. HOSPITAL
-- =====================================================

CREATE TABLE hospital (
    hospital_id INT AUTO_INCREMENT PRIMARY KEY,
    hospital_name VARCHAR(150) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(15) NOT NULL,
    email VARCHAR(100),
    address VARCHAR(255)
);


-- =====================================================
-- 8. HOSPITAL REQUEST
-- =====================================================

CREATE TABLE hospital_request (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    hospital_id INT NOT NULL,
    blood_group_id INT NOT NULL,
    component_id INT NOT NULL,
    quantity_ml INT NOT NULL,
    request_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    emergency_level VARCHAR(20) DEFAULT 'Normal',
    request_status VARCHAR(30) DEFAULT 'Pending',
    required_date DATE,

    FOREIGN KEY (hospital_id)
        REFERENCES hospital(hospital_id),

    FOREIGN KEY (blood_group_id)
        REFERENCES blood_group(blood_group_id),

    FOREIGN KEY (component_id)
        REFERENCES blood_component(component_id)
);


-- =====================================================
-- 9. MATCHING
-- =====================================================

CREATE TABLE matching (
    matching_id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    unit_id INT NOT NULL,
    matched_quantity_ml INT NOT NULL,
    matching_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    matching_status VARCHAR(30) DEFAULT 'Matched',

    FOREIGN KEY (request_id)
        REFERENCES hospital_request(request_id),

    FOREIGN KEY (unit_id)
        REFERENCES blood_unit(unit_id)
);


-- =====================================================
-- 10. RESERVATION
-- =====================================================

CREATE TABLE reservation (
    reservation_id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    unit_id INT NOT NULL,
    reserved_quantity_ml INT NOT NULL,
    reservation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    reservation_status VARCHAR(30) DEFAULT 'Reserved',

    FOREIGN KEY (request_id)
        REFERENCES hospital_request(request_id),

    FOREIGN KEY (unit_id)
        REFERENCES blood_unit(unit_id)
);


-- =====================================================
-- 11. DISTRIBUTION
-- =====================================================

CREATE TABLE distribution (
    distribution_id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    unit_id INT NOT NULL,
    hospital_id INT NOT NULL,
    distributed_quantity_ml INT NOT NULL,
    distribution_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    received_by VARCHAR(100),

    FOREIGN KEY (request_id)
        REFERENCES hospital_request(request_id),

    FOREIGN KEY (unit_id)
        REFERENCES blood_unit(unit_id),

    FOREIGN KEY (hospital_id)
        REFERENCES hospital(hospital_id)
);


-- =====================================================
-- INSERT BASIC BLOOD GROUPS
-- =====================================================

INSERT INTO blood_group (blood_group)
VALUES
('A+'),
('A-'),
('B+'),
('B-'),
('AB+'),
('AB-'),
('O+'),
('O-');


-- =====================================================
-- INSERT BLOOD COMPONENTS
-- =====================================================

INSERT INTO blood_component (component_name, description)
VALUES
('Whole Blood', 'Complete blood unit'),
('RBC', 'Red Blood Cells'),
('Plasma', 'Blood plasma'),
('Platelets', 'Platelet component');


-- =====================================================
-- SAMPLE STORAGE LOCATIONS
-- =====================================================

INSERT INTO storage_location
(location_name, refrigerator_number, shelf_number)
VALUES
('Blood Bank Room A', 'REF-01', 'S1'),
('Blood Bank Room A', 'REF-01', 'S2'),
('Blood Bank Room B', 'REF-02', 'S1');