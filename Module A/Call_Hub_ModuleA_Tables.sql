CREATE DATABASE Module_A1_;
USE Module_A1_;

CREATE TABLE Departments (
    dept_id INT PRIMARY KEY AUTO_INCREMENT,
    dept_code VARCHAR(10) NOT NULL UNIQUE,
    dept_name VARCHAR(100) NOT NULL,
    building_location VARCHAR(100) NOT NULL,
    is_academic BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE Data_Categories (
    category_id INT PRIMARY KEY AUTO_INCREMENT,
    category_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE Roles (
    role_id INT PRIMARY KEY AUTO_INCREMENT,
    role_title VARCHAR(50) NOT NULL UNIQUE,
    can_edit_others BOOLEAN NOT NULL DEFAULT 0,
    can_view_logs BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE Role_Permissions (
    permission_id INT PRIMARY KEY AUTO_INCREMENT,
    role_id INT,
    category_id INT NOT NULL,
    can_view BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (role_id) REFERENCES Roles(role_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES Data_Categories(category_id)
);

CREATE TABLE Members (
    member_id INT PRIMARY KEY AUTO_INCREMENT,
    full_name VARCHAR(100) NOT NULL,
    designation VARCHAR(100),
    profile_image_url VARCHAR(255) DEFAULT 'default_avatar.png',
    age INT NOT NULL CHECK (age >= 16),
    gender ENUM('M', 'F', 'O') NOT NULL,
    dept_id INT NOT NULL,
    join_date DATE NOT NULL DEFAULT (CURRENT_DATE),
    is_active INT NOT NULL DEFAULT 1,
    is_deleted BOOLEAN NOT NULL DEFAULT 0,
    deleted_at DATETIME DEFAULT NULL,
    FOREIGN KEY (dept_id) REFERENCES Departments(dept_id)
);

CREATE TABLE Member_Role_Assignments (
    assignment_id INT PRIMARY KEY AUTO_INCREMENT,
    member_id INT NOT NULL,
    role_id INT NOT NULL,
    
    assigned_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES Members(member_id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES Roles(role_id)
    
);

CREATE TABLE Contact_Details (
    contact_id INT PRIMARY KEY AUTO_INCREMENT,
    member_id INT NOT NULL,
    contact_type ENUM('Mobile', 'Personal Email', 'Landline', 'Official Email') NOT NULL,
    contact_value VARCHAR(150) NOT NULL,
    category_id INT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (member_id) REFERENCES Members(member_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES Data_Categories(category_id)
);

CREATE TABLE Locations (
    location_id INT PRIMARY KEY AUTO_INCREMENT,
    member_id INT NOT NULL,
    location_type ENUM('Office', 'Hostel Room', 'Lab', 'Residence', 'Post') NOT NULL,
    building_name VARCHAR(100) NOT NULL,
    room_number VARCHAR(50) NOT NULL,
    category_id INT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES Members(member_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES Data_Categories(category_id)
);

CREATE TABLE Emergency_Contacts (
    record_id INT PRIMARY KEY AUTO_INCREMENT,
    member_id INT NOT NULL,
    contact_person_name VARCHAR(100) NOT NULL,
    relation VARCHAR(50) NOT NULL,
    emergency_phone VARCHAR(20) NOT NULL,
    category_id INT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES Members(member_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES Data_Categories(category_id)
);

CREATE TABLE Search_Logs (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    searched_term VARCHAR(100) NOT NULL,
    searched_by_member_id INT,
    results_found_count INT NOT NULL DEFAULT 0,
    search_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (searched_by_member_id) REFERENCES Members(member_id) ON DELETE SET NULL
);

CREATE TABLE Audit_Trail (
    audit_id INT PRIMARY KEY AUTO_INCREMENT,
    actor_id INT NOT NULL,
    target_table VARCHAR(50) NOT NULL,
    target_record_id INT NOT NULL,
    action_type ENUM('INSERT', 'UPDATE', 'DELETE', 'SOFT_DELETE') NOT NULL,
    action_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actor_id) REFERENCES Members(member_id)
);

-- DEPARTMENTS 
INSERT INTO Departments (dept_code, dept_name, building_location, is_academic) VALUES
('CSE', 'Computer Science & Engg', 'Ada Lovelace Block', 1),
('EE', 'Electrical Engineering', 'Tesla Hall', 1),
('ME', 'Mechanical Engineering', 'Visvesvaraya Workshop', 1),
('CE', 'Civil Engineering', 'Ramanujan Building', 1),
('CHEM', 'Chemical Engineering', 'Curie Lab Complex', 1),
('BIO', 'Biotechnology', 'Darwin Wing', 1),
('PHY', 'Physics', 'Newton Block', 1),
('MATH', 'Mathematics', 'Ramanujan Building', 1),
('ADMIN', 'Central Administration', 'Main Admin Wing', 0),
('HSTL', 'Hostel Administration', 'Student Activity Center', 0),
('MED', 'Health Center', 'Dhanvantari Medical Unit', 0),
('SEC', 'Security', 'Main Gate Complex', 0),
('LIB', 'Central Library', 'Knowledge Center', 0),
('SPORT', 'Sports & PE', 'Gymkhana Ground', 0),
('MAINT', 'Estate & Maintenance', 'Service Block B', 0);

-- CATEGORIES 
INSERT INTO Data_Categories (category_name) VALUES
('Public'), ('Residential'), ('Academic'), ('Confidential'), ('Emergency');

-- ROLES 
INSERT INTO Roles (role_title, can_edit_others, can_view_logs) VALUES
('Director', 1, 1),
('Dean Academics', 1, 1),
('Dean Student Welfare', 1, 1),
('Registrar', 1, 1),
('HOD', 1, 0),
('Professor', 0, 0),
('Asst. Professor', 0, 0),
('Student (UG)', 0, 0),
('Student (PG/PhD)', 0, 0),
('Warden', 0, 0),
('Security Guard', 0, 0),
('Medical Staff', 0, 0);

-- Director (Role 1): Sees Categories 1, 2, 3, 4, 5
INSERT INTO Role_Permissions (role_id, category_id, can_view) VALUES
(1,1,1),(1,2,1),(1,3,1),(1,4,1),(1,5,1),

-- Dean Academics (Role 2): Sees 1, 3, 4 | Cannot see 2, 5
(2,1,1),(2,2,0),(2,3,1),(2,4,1),(2,5,0),

-- Dean Student Welfare (Role 3): Sees 1,2| Cannot see 3,4,5
(3,1,1),(3,2,1),(3,3,0),(3,4,0),(3,5,0),

-- Registrar (Role 4): Sees 1,2,3 | Cannot see 4,5
(4,1,1),(4,2,1),(4,3,1),(4,4,0),(4,5,0),

-- HOD (Role 5): Sees 1, 3 | Cannot see 2, 4, 5
(5,1,1),(5,2,0),(5,3,1),(5,4,0),(5,5,0),

-- Professor (Role 6): Sees 1,3 | Cannot see 2,4,5
(6,1,1),(6,2,0),(6,3,1),(6,4,0),(6,5,0),

-- Asst. Professor (Role 7): Sees 1,3 | Cannot see 2,4,5
(7,1,1),(7,2,0),(7,3,1),(7,4,0),(7,5,0),

-- Student (Role 8): Sees 1 | Cannot see 2, 3, 4, 5
(8,1,1),(8,2,0),(8,3,0),(8,4,0),(8,5,0),

-- Student (PG/PhD) (Role 9): Sees 1 | Cannot see 2,3,4,5
(9,1,1),(9,2,0),(9,3,0),(9,4,0),(9,5,0),

-- Warden (Role 10): Sees 2, 5 | Cannot see 1, 3, 4
(10,1,0),(10,2,1),(10,3,0),(10,4,0),(10,5,1),

-- Security (Role 11): Sees 1, 5 | Cannot see 2, 3, 4
(11,1,1),(11,2,0),(11,3,0),(11,4,0),(11,5,1),

-- Doctor (Role 12): Sees  5 | Cannot see 1, 2, 3, 4
(12,1,0),(12,2,0),(12,3,0),(12,4,0),(12,5,1);

-- MEMBERS 
INSERT INTO Members (full_name, designation, age, gender, dept_id) VALUES
-- Admin
('Prof. Arvind Mishra', 'Director', 58, 'M', 9),     
('Dr. Sarah Joseph', 'Dean Academics', 52, 'F', 9),  
('Mr. Rakesh Kapoor', 'Registrar', 48, 'M', 9),      
-- Faculty
('Dr. H.C. Verma', 'HOD Physics', 60, 'M', 7),       
('Dr. Anita Roy', 'Professor CSE', 45, 'F', 1),      
('Dr. Ken Adams', 'Asst. Prof EE', 34, 'M', 2),      
('Dr. Meera Reddy', 'HOD Biotech', 49, 'F', 6),      
('Dr. S. Ramanujan', 'Professor Math', 55, 'M', 8),  
-- Students (UG)
('Vihaan Malhotra', 'BTech CSE 3rd Yr', 20, 'M', 1), 
('Riya Sen', 'BTech EE 2nd Yr', 19, 'F', 2),         
('Arjun Das', 'BTech ME 4th Yr', 21, 'M', 3),        
('Kabir Singh', 'BTech Civil 1st Yr', 18, 'M', 4),   
('Ananya Gupta', 'BTech CSE 3rd Yr', 20, 'F', 1),   
('Rohan Mehra', 'BTech Chem 2nd Yr', 19, 'M', 5),    
-- Students (PG/PhD)
('Sneha Iyer', 'PhD Physics', 26, 'F', 7),          
('Vikram Rathore', 'MTech CSE', 23, 'M', 1),         
-- Staff
('Mr. Baldev Singh', 'Chief Warden', 50, 'M', 10),   
('Mrs. Geeta Ben', 'Warden Girls Hostel', 45, 'F', 10), 
('Rajesh Kumar', 'Head Security', 42, 'M', 12),     
('Suresh Patil', 'Gate Guard', 35, 'M', 12),         
('Dr. Elena Thomas', 'Medical Officer', 39, 'F', 11),
('Sister Mary', 'Head Nurse', 30, 'F', 11),        
('Dr. Ananya Sharma', 'Dean Student Welfare', 40, 'F', 1);


-- ASSIGNMENTS 
INSERT INTO Member_Role_Assignments (member_id, role_id, assigned_date) VALUES
-- 1. ADMINS
(1, 1, '2020-01-15'), 
(2, 2, '2020-02-20'),  
(3, 4, '2021-06-10'),  

-- 2. FACULTY 
(4, 5, '2021-08-01'),  
(5, 6, '2022-01-15'),  
(6, 7, '2019-11-30'),  
(7, 5, '2023-03-12'),  
(8, 6, '2020-09-05'),  

-- 3. STUDENTS (UG) -> Role 8
(9, 8, '2024-08-01'),
(10, 8, '2024-08-01'), 
(11, 8, '2023-08-01'), 
(12, 8, '2025-08-01'), 
(13, 8, '2022-08-01'), 
(14, 8, '2023-08-01'), 

-- 4. STUDENTS (PG) -> Role 9
(15, 9, '2023-07-15'), 
(16, 9, '2023-07-15'), 

-- 5. WARDENS -> Role 10
(17, 10, '2021-05-20'),
(18, 10, '2022-11-11'), 

-- 6. SECURITY -> Role 11
(19, 11, '2020-03-15'), 
(20, 11, '2023-01-10'), 

-- 7. MEDICAL -> Role 12
(21, 12, '2019-12-01'), 
(22, 12, '2024-02-28'), 

-- Dean Welfare
(23, 3, '2023-02-28'); 



-- CONTACT DETAILS 
INSERT INTO Contact_Details (member_id, contact_type, contact_value, category_id, is_primary) VALUES
-- Admin
(1, 'Official Email', 'director@inst.ac.in', 1, 1),
(2, 'Official Email', 'dean.acad@inst.ac.in', 1, 1),
(3, 'Official Email', 'registrar@inst.ac.in', 1, 1),

-- Faculty
(4, 'Official Email', 'hcverma@phy.inst.ac.in', 1, 1),
(5, 'Official Email', 'anita.cse@inst.ac.in', 1, 1),
(6, 'Official Email', 'ken.adams@ee.inst.ac.in', 1, 1),
(7, 'Official Email', 'meera.bio@inst.ac.in', 1, 1),
(8, 'Official Email', 'ramanujan@math.inst.ac.in', 1, 1),

-- Students
(9, 'Mobile', '9876543210', 2, 1),
(10, 'Mobile', '9876543211', 2, 1),
(11, 'Mobile', '9876543212', 2, 1),
(12, 'Mobile', '9876543213', 2, 1),
(13, 'Mobile', '9876543214', 2, 1),
(14, 'Mobile', '9876543215', 2, 1),
(15, 'Mobile', '9876543216', 2, 1),
(16, 'Mobile', '9876543217', 2, 1),

-- Staff
(17, 'Landline', '079-2345678', 1, 1), 
(19, 'Landline', 'SEC-01', 5, 1),      
(21, 'Landline', '108', 5, 1),         
(22, 'Mobile', '9876543220', 2, 1),    
(23, 'Official Email', 'welfare.secretary@iitgn.ac.in', 1, 1);    

-- LOCATIONS 
INSERT INTO Locations (member_id, location_type, building_name, room_number, category_id) VALUES
-- Admin 
(1, 'Office', 'Main Admin Wing', '101 (Director)', 1),
(2, 'Office', 'Main Admin Wing', '102 (Dean)', 1),
(3, 'Office', 'Main Admin Wing', '103 (Registrar)', 1),

-- Faculty 
(4, 'Office', 'Newton Block', 'Phy-101', 1), 
(5, 'Office', 'Ada Lovelace Block', 'CSE-304', 1), 
(6, 'Office', 'Tesla Hall', 'EE-205', 1), 
(7, 'Lab', 'Darwin Wing', 'Bio-Lab-3', 1), 
(8, 'Office', 'Ramanujan Building', 'Math-204', 1), 

-- Students 
(9, 'Hostel Room', 'Himalaya Hostel', 'H-101', 2),
(10, 'Hostel Room', 'Ganga Hostel', 'G-202', 2),
(11, 'Hostel Room', 'Himalaya Hostel', 'H-305', 2),
(12, 'Hostel Room', 'Himalaya Hostel', 'H-102', 2),
(13, 'Hostel Room', 'Ganga Hostel', 'G-105', 2),
(14, 'Hostel Room', 'Himalaya Hostel', 'H-401', 2),
(15, 'Hostel Room', 'Married Scholar Apts', 'A-12', 2), 
(16, 'Hostel Room', 'Himalaya Hostel', 'H-500', 2),

-- Staff Locations
(17, 'Office', 'Himalaya Hostel', 'Warden Off', 1),
(18, 'Office', 'Ganga Hostel', 'Warden Off', 1),
(19, 'Office', 'Main Gate Complex', 'Security HQ', 1),
(20, 'Post', 'Main Gate Complex', 'Post-1', 1), 
(21, 'Office', 'Dhanvantari Medical Unit', 'OPD-1', 1),
(22, 'Office', 'Dhanvantari Medical Unit', 'Nursing Stn', 1),
(23, 'Office', 'Main Admin Wing', '104', 1);


-- SEARCH LOGS 
INSERT INTO Search_Logs (searched_term, searched_by_member_id, results_found_count) VALUES
('Prof. Arvind Mishra', 1, 1),
('Riya Sen', 10, 1),
('Rohan Mehra', 14, 1),
('Prof. Arvind Mishra', 1, 2),
('Ananya Gupta', 13, 1),
('Riya Sen', 10, 2),
('Dr. Ken Adams', 6, 1),
('Ananya Gupta', 13, 2),
('Suresh Patil', 20, 1),
('Prof. Arvind Mishra', 1, 3),
('Riya Sen', 10, 3);


-- EMERGENCY CONTACTS 
INSERT INTO Emergency_Contacts (member_id, contact_person_name, relation, emergency_phone, category_id) VALUES
-- STUDENTS 
(9, 'Raj Malhotra', 'Father', '9988112233', 5),      
(10, 'Sunita Sen', 'Mother', '9988112234', 5),        
(11, 'Kiran Das', 'Father', '9988112235', 5),       
(12, 'Vikram Singh', 'Father', '9988112236', 5),     
(13, 'Rahul Gupta', 'Father', '9988112237', 5),       
(14, 'Mohit Mehra', 'Brother', '9988112238', 5),    
(16, 'Mr. Rathore', 'Father', '9988112299', 5),       

-- FACULTY & ADMIN 
(1, 'Mrs. Mishra', 'Wife', '9988112241', 5),          
(2, 'Mr. Joseph', 'Husband', '9988112255', 5),        
(4, 'Mrs. Verma', 'Wife', '9988112244', 5),           
(5, 'Mr. Roy', 'Husband', '9988112242', 5),          
(6, 'Mrs. Adams', 'Wife', '9988112243', 5),           
(7, 'Mr. Reddy', 'Husband', '9988112266', 5),        
(15, 'Karthik Iyer', 'Spouse', '9988112239', 5),      

-- STAFF 
(17, 'Mrs. Singh', 'Wife', '9988112277', 5),          
(19, 'Mrs. Kumar', 'Wife', '9988112288', 5),         
(21, 'Dr. John', 'Husband', '9988112240', 5);       

-- AUDIT TRAIL 
INSERT INTO Audit_Trail (actor_id, target_table, target_record_id, action_type) VALUES
(3, 'Members', 9, 'INSERT'),
(3, 'Members', 10, 'INSERT'),
(3, 'Members', 11, 'INSERT'),
(1, 'Role_Permissions', 4, 'UPDATE'),
(23, 'Locations', 19, 'UPDATE'),
(3, 'Contact_Details', 17, 'UPDATE'),
(1, 'Emergency_Contacts', 15, 'INSERT'),
(3, 'Members', 20, 'SOFT_DELETE'), 
(3, 'Members', 20, 'UPDATE'), 
(1, 'Roles', 2, 'UPDATE'),
(3, 'Search_Logs', 1, 'DELETE'),
(23, 'Locations', 15, 'UPDATE');