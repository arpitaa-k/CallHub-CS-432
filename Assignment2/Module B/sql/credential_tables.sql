USE Module_A1_Final;


CREATE TABLE User_Credentials (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    member_id INT NOT NULL UNIQUE, 
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    FOREIGN KEY (member_id) REFERENCES Members(member_id) ON DELETE CASCADE
);

