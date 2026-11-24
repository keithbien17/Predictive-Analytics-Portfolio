
-- =====================================================
-- PULSE FITNESS DATABASE
-- Complete SQL Script
-- =====================================================

USE assignment;

-- =====================================================
-- PART 1: DROP EXISTING PULSE FITNESS TABLES
-- =====================================================

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS Member_Class;
DROP TABLE IF EXISTS Trainer_Class;
DROP TABLE IF EXISTS Payment;
DROP TABLE IF EXISTS Membership;
DROP TABLE IF EXISTS Class;
DROP TABLE IF EXISTS Trainer;
DROP TABLE IF EXISTS Member;

SET FOREIGN_KEY_CHECKS = 1;


-- =====================================================
-- PART 2: CREATE DATABASE TABLES
-- =====================================================

-- TABLE 1: MEMBER

CREATE TABLE Member (
    member_id INT PRIMARY KEY,
    phone VARCHAR(15),
    full_name VARCHAR(100),
    email VARCHAR(100)
);


-- TABLE 2: TRAINER

CREATE TABLE Trainer (
    trainer_id INT PRIMARY KEY,
    trainer_name VARCHAR(100),
    phone VARCHAR(15),
    certification VARCHAR(100)
);


-- TABLE 3: CLASS

CREATE TABLE Class (
    class_id INT PRIMARY KEY,
    class_type VARCHAR(50),
    room VARCHAR(50),
    schedule_time DATETIME
);


-- TABLE 4: MEMBERSHIP

CREATE TABLE Membership (
    membership_id INT PRIMARY KEY,
    member_id INT UNIQUE,
    status VARCHAR(20),
    join_date DATE,
    membership_type VARCHAR(50),
    access_limitations VARCHAR(100),
    FOREIGN KEY (member_id)
        REFERENCES Member(member_id)
);


-- TABLE 5: PAYMENT

CREATE TABLE Payment (
    payment_id INT PRIMARY KEY,
    member_id INT,
    payment_date DATE,
    plan_id INT,
    amount DECIMAL(10,2),
    payment_method VARCHAR(50),
    FOREIGN KEY (member_id)
        REFERENCES Member(member_id)
);


-- TABLE 6: TRAINER_CLASS

CREATE TABLE Trainer_Class (
    trainer_id INT,
    class_id INT,
    PRIMARY KEY (trainer_id, class_id),
    FOREIGN KEY (trainer_id)
        REFERENCES Trainer(trainer_id),
    FOREIGN KEY (class_id)
        REFERENCES Class(class_id)
);


-- TABLE 7: MEMBER_CLASS

CREATE TABLE Member_Class (
    member_id INT,
    class_id INT,
    PRIMARY KEY (member_id, class_id),
    FOREIGN KEY (member_id)
        REFERENCES Member(member_id),
    FOREIGN KEY (class_id)
        REFERENCES Class(class_id)
);


-- =====================================================
-- PART 3: INSERT SAMPLE DATA
-- =====================================================

-- MEMBER DATA

INSERT INTO Member
(member_id, phone, full_name, email)
VALUES
(1, '123-456-7890', 'Taylor Swift', 'taylor.swift@gmail.com'),
(2, '987-654-3210', 'Selena Gomez', 'selena.gomez@gmail.com'),
(3, '555-123-4567', 'Miley Cyrus', 'miley.cyrus@gmail.com'),
(4, '666-234-5678', 'Bruno Mars', 'bruno.mars@gmail.com'),
(5, '777-345-6789', 'Harry Styles', 'harry.styles@gmail.com');


-- CLASS DATA

INSERT INTO Class
(class_id, class_type, room, schedule_time)
VALUES
(1, 'Yoga', 'Room A', '2025-05-01 08:00:00'),
(2, 'Zumba', 'Room B', '2025-05-01 09:30:00'),
(3, 'CrossFit', 'Room C', '2025-05-01 10:30:00'),
(4, 'Pilates', 'Room D', '2025-05-02 08:00:00'),
(5, 'Spin', 'Room E', '2025-05-02 11:00:00');


-- TRAINER DATA

INSERT INTO Trainer
(trainer_id, trainer_name, phone, certification)
VALUES
(1, 'David Johnson', '111-222-3333', 'Certified Yoga Instructor'),
(2, 'Michelle Lee', '444-555-6666', 'Certified CrossFit Trainer'),
(3, 'Hannah Kim', '777-888-9999', 'Certified Zumba Instructor'),
(4, 'Emma Roberts', '555-555-5555', 'Certified Pilates Instructor'),
(5, 'Andrei Clark', '333-333-3333', 'Certified Spin Instructor');


-- TRAINER_CLASS DATA

INSERT INTO Trainer_Class
(trainer_id, class_id)
VALUES
(1, 1),
(2, 3),
(3, 2),
(4, 4),
(5, 5);


-- MEMBERSHIP DATA

INSERT INTO Membership
(membership_id, member_id, status, join_date,
 membership_type, access_limitations)
VALUES
(1, 1, 'Active', '2025-04-01', 'Premium',
 'Full access, unlimited classes'),

(2, 2, 'Active', '2025-04-05', 'Basic',
 'Access to 2 classes per week'),

(3, 3, 'Active', '2025-04-07', 'Student',
 'Access to 3 classes per week, off-peak hours'),

(4, 4, 'Inactive', '2025-01-10', 'Premium',
 'Full access, unlimited classes'),

(5, 5, 'Active', '2025-04-10', 'Basic',
 'Access to 2 classes per week');


-- PAYMENT DATA

INSERT INTO Payment
(payment_id, member_id, payment_date, plan_id,
 amount, payment_method)
VALUES
(1, 1, '2025-04-01', 1, 120.00, 'Credit Card'),
(2, 2, '2025-04-05', 2, 60.00, 'Debit Card'),
(3, 3, '2025-04-07', 3, 70.00, 'PayPal'),
(4, 4, '2025-01-15', 1, 120.00, 'Credit Card'),
(5, 5, '2025-04-10', 2, 60.00, 'Debit Card');


-- MEMBER_CLASS DATA
-- Sample class attendance records

INSERT INTO Member_Class
(member_id, class_id)
VALUES
(1, 1),
(1, 2),
(1, 3),
(2, 1),
(2, 2),
(3, 1),
(3, 3),
(4, 4),
(5, 2),
(5, 5);


-- =====================================================
-- PART 4: SEVEN MAIN BUSINESS CONCERN QUERIES
-- =====================================================

-- QUERY 1: SEASONAL MEMBERSHIP TRENDS
-- Analyzing membership fluctuations by month

SELECT
    MONTH(join_date) AS month,
    COUNT(member_id) AS total_members
FROM Membership
GROUP BY MONTH(join_date)
ORDER BY month;


-- QUERY 2: CLASS DEMAND
-- Identifying underutilized and overbooked classes

SELECT
    c.class_type,
    COUNT(mc.member_id) AS total_attendance
FROM Class c
LEFT JOIN Member_Class mc
    ON c.class_id = mc.class_id
GROUP BY c.class_id, c.class_type
HAVING total_attendance < 5
    OR total_attendance > 20;


-- QUERY 3: MEMBERSHIP PRICING STRATEGIES
-- Analyzing revenue by membership type

SELECT
    m.membership_type,
    COUNT(p.payment_id) AS total_payments,
    SUM(p.amount) AS total_revenue
FROM Payment p
JOIN Membership m
    ON p.member_id = m.member_id
GROUP BY m.membership_type
ORDER BY total_revenue DESC;


-- QUERY 4: CUSTOMER RETENTION
-- Identifying active members with low attendance

SELECT
    m.member_id,
    m.full_name,
    COUNT(mc.class_id) AS classes_attended,
    mem.status
FROM Member m
JOIN Membership mem
    ON m.member_id = mem.member_id
LEFT JOIN Member_Class mc
    ON m.member_id = mc.member_id
WHERE mem.status = 'Active'
GROUP BY
    m.member_id,
    m.full_name,
    mem.status
HAVING classes_attended < 3;


-- QUERY 5: REVENUE GENERATION
-- Total revenue by membership type

SELECT
    m.membership_type,
    SUM(p.amount) AS total_revenue
FROM Payment p
JOIN Membership m
    ON p.member_id = m.member_id
GROUP BY m.membership_type
ORDER BY total_revenue DESC;


-- QUERY 6: RESOURCE UTILIZATION
-- Identifying underutilized trainers and rooms

SELECT
    t.trainer_name,
    c.room,
    COUNT(mc.member_id) AS total_attendance
FROM Trainer t
JOIN Trainer_Class tc
    ON t.trainer_id = tc.trainer_id
JOIN Class c
    ON tc.class_id = c.class_id
LEFT JOIN Member_Class mc
    ON c.class_id = mc.class_id
GROUP BY
    t.trainer_id,
    t.trainer_name,
    c.room
HAVING total_attendance < 5;


-- QUERY 7: CLASS ATTENDANCE PATTERNS
-- Analyzing attendance by class schedule

SELECT
    c.schedule_time,
    COUNT(mc.member_id) AS attendance_count
FROM Class c
LEFT JOIN Member_Class mc
    ON c.class_id = mc.class_id
GROUP BY
    c.class_id,
    c.schedule_time
ORDER BY attendance_count DESC;


-- =====================================================
-- PART 5: ADDITIONAL ANALYSIS QUERIES
-- =====================================================

-- ADDITIONAL QUERY 1:
-- Seasonal membership trends by year and month

SELECT
    YEAR(join_date) AS year,
    MONTH(join_date) AS month,
    COUNT(member_id) AS new_members
FROM Membership
GROUP BY
    YEAR(join_date),
    MONTH(join_date)
ORDER BY year, month;


-- ADDITIONAL QUERY 2:
-- Monthly revenue generation

SELECT
    YEAR(payment_date) AS year,
    MONTH(payment_date) AS month,
    SUM(amount) AS monthly_revenue
FROM Payment
GROUP BY
    YEAR(payment_date),
    MONTH(payment_date)
ORDER BY year, month;


-- ADDITIONAL QUERY 3:
-- Most popular classes

SELECT
    c.class_type,
    COUNT(mc.member_id) AS total_attendance
FROM Class c
LEFT JOIN Member_Class mc
    ON c.class_id = mc.class_id
GROUP BY
    c.class_id,
    c.class_type
HAVING total_attendance > 20;


-- ADDITIONAL QUERY 4:
-- Underutilized classes

SELECT
    c.class_type,
    COUNT(mc.member_id) AS total_attendance
FROM Class c
LEFT JOIN Member_Class mc
    ON c.class_id = mc.class_id
GROUP BY
    c.class_id,
    c.class_type
HAVING total_attendance < 5;


-- =====================================================
-- PART 6: DATABASE VERIFICATION
-- =====================================================

-- Check all tables

SHOW TABLES;


-- Check table structures

DESCRIBE Member;
DESCRIBE Trainer;
DESCRIBE Class;
DESCRIBE Trainer_Class;
DESCRIBE Member_Class;
DESCRIBE Membership;
DESCRIBE Payment;


-- Check inserted records

SELECT * FROM Member;
SELECT * FROM Trainer;
SELECT * FROM Class;
SELECT * FROM Trainer_Class;
SELECT * FROM Member_Class;
SELECT * FROM Membership;
SELECT * FROM Payment;

-- =====================================================
-- END OF PULSE FITNESS SQL SCRIPT
-- =====================================================
