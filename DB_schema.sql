-- ============================================================================
-- Fashion Business Database Schema (corrected)
-- - Minimal corrections only:
--   * Fixed Sold_In sample insert rows so sale_id ↔ item_id align with Sales.
--   * Added UNIQUE constraint on Inventory(item_id) to ensure one inventory row per item.
-- ============================================================================

-- Create Designers table
CREATE TABLE IF NOT EXISTS Designers (
    designer_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(20),
    style VARCHAR(50)
);

-- Create Collections table
CREATE TABLE IF NOT EXISTS Collections (
    collection_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    season VARCHAR(50),
    year INT,
    designer_id INT,
    FOREIGN KEY (designer_id) REFERENCES Designers(designer_id)
);

-- Create Suppliers table
CREATE TABLE IF NOT EXISTS Suppliers (
    supplier_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(20),
    address TEXT
);

-- Create Fabrics table
CREATE TABLE IF NOT EXISTS Fabrics (
    fabric_id INT PRIMARY KEY AUTO_INCREMENT,
    material VARCHAR(100) NOT NULL,
    supplier_id INT,
    cost_per_meter DECIMAL(10, 2),
    FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id)
);

-- Create Clothing Items table
CREATE TABLE IF NOT EXISTS Clothing_Items (
    item_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    size VARCHAR(20),
    color VARCHAR(50),
    price DECIMAL(10, 2),
    collection_id INT,
    FOREIGN KEY (collection_id) REFERENCES Collections(collection_id)
);

-- Create Stores table
CREATE TABLE IF NOT EXISTS Stores (
    store_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(200),
    manager VARCHAR(100)
);

-- Create Sales table
CREATE TABLE IF NOT EXISTS Sales (
    sale_id INT PRIMARY KEY AUTO_INCREMENT,
    sale_date DATE NOT NULL,
    store_id INT,
    item_id INT,
    quantity_sold INT,
    total_amount DECIMAL(10, 2),
    payment VARCHAR(50),
    FOREIGN KEY (store_id) REFERENCES Stores(store_id),
    FOREIGN KEY (item_id) REFERENCES Clothing_Items(item_id)
);

-- Create Inventory table
CREATE TABLE IF NOT EXISTS Inventory (
    inventory_id INT PRIMARY KEY AUTO_INCREMENT,
    item_id INT,
    quantity_in_stock INT,
    reorder_level INT,
    FOREIGN KEY (item_id) REFERENCES Clothing_Items(item_id)
);

-- Create junction table for Suppliers and Fabrics (supplies relationship)
CREATE TABLE IF NOT EXISTS Supplies (
    supplier_id INT,
    fabric_id INT,
    PRIMARY KEY (supplier_id, fabric_id),
    FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id),
    FOREIGN KEY (fabric_id) REFERENCES Fabrics(fabric_id)
);

-- Create junction table for Fabrics and Clothing Items (uses relationship)
CREATE TABLE IF NOT EXISTS Uses (
    fabric_id INT,
    item_id INT,
    PRIMARY KEY (fabric_id, item_id),
    FOREIGN KEY (fabric_id) REFERENCES Fabrics(fabric_id),
    FOREIGN KEY (item_id) REFERENCES Clothing_Items(item_id)
);

-- Create junction table for Clothing Items and Fabrics with quantity (Clothing_Item_Fabrics)
CREATE TABLE IF NOT EXISTS Clothing_Item_Fabrics (
    cf_id INT PRIMARY KEY AUTO_INCREMENT,
    item_id INT,
    fabric_id INT,
    quantity_used DECIMAL(10, 2),
    FOREIGN KEY (item_id) REFERENCES Clothing_Items(item_id),
    FOREIGN KEY (fabric_id) REFERENCES Fabrics(fabric_id)
);

-- Create junction table for Collections and Clothing Items (contain relationship)
CREATE TABLE IF NOT EXISTS Contains (
    collection_id INT,
    item_id INT,
    PRIMARY KEY (collection_id, item_id),
    FOREIGN KEY (collection_id) REFERENCES Collections(collection_id),
    FOREIGN KEY (item_id) REFERENCES Clothing_Items(item_id)
);

-- Create junction table for Clothing Items and Inventory (tracked by relationship)
CREATE TABLE IF NOT EXISTS Tracked_By (
    item_id INT,
    inventory_id INT,
    PRIMARY KEY (item_id, inventory_id),
    FOREIGN KEY (item_id) REFERENCES Clothing_Items(item_id),
    FOREIGN KEY (inventory_id) REFERENCES Inventory(inventory_id)
);

-- Create junction table for Stores and Sales (occurs at relationship)
CREATE TABLE IF NOT EXISTS Occurs_At (
    sale_id INT,
    store_id INT,
    PRIMARY KEY (sale_id, store_id),
    FOREIGN KEY (sale_id) REFERENCES Sales(sale_id),
    FOREIGN KEY (store_id) REFERENCES Stores(store_id)
);

-- Create junction table for Clothing Items and Sales (sold in relationship)
CREATE TABLE IF NOT EXISTS Sold_In (
    item_id INT,
    sale_id INT,
    PRIMARY KEY (item_id, sale_id),
    FOREIGN KEY (item_id) REFERENCES Clothing_Items(item_id),
    FOREIGN KEY (sale_id) REFERENCES Sales(sale_id)
);

-- Create junction table for Designers and Collections (creates relationship)
CREATE TABLE IF NOT EXISTS Creates (
    designer_id INT,
    collection_id INT,
    PRIMARY KEY (designer_id, collection_id),
    FOREIGN KEY (designer_id) REFERENCES Designers(designer_id),
    FOREIGN KEY (collection_id) REFERENCES Collections(collection_id)
);

-- ============================================================================
-- SAMPLE DATA INSERTION (original sample data preserved; Sold_In rows corrected)
-- ============================================================================

-- Insert Designers
INSERT INTO Designers (name, email, phone, style) VALUES
('Sabyasachi Mukherjee', 'sabyasachi@fashion.in', '+91-98765-43210', 'Indo-Western'),
('Manish Malhotra', 'manish.malhotra@design.in', '+91-98765-43211', 'Traditional'),
('Anita Dongre', 'anita.dongre@couture.in', '+91-98765-43212', 'Contemporary Ethnic'),
('Rohit Bal', 'rohit.bal@style.in', '+91-98765-43213', 'Fusion'),
('Tarun Tahiliani', 'tarun.tahiliani@fashion.in', '+91-98765-43214', 'Bridal Couture');

-- Insert Collections
INSERT INTO Collections (name, season, year, designer_id) VALUES
('Festive Splendor', 'Diwali', 2024, 1),
('Heritage Weaves', 'Wedding Season', 2024, 2),
('Modern Sarees', 'Summer', 2024, 3),
('Royal Sherwanis', 'Winter Wedding', 2024, 4),
('Bridal Dreams', 'Wedding Season', 2024, 5);

-- Insert Suppliers
INSERT INTO Suppliers (name, email, phone, address) VALUES
('Surat Silk Mills', 'info@suratsilk.in', '+91-261-2345678', 'Ring Road, Surat, Gujarat'),
('Kanchipuram Handlooms', 'sales@kanchipuram.in', '+91-44-27345678', 'Gandhi Road, Kanchipuram, Tamil Nadu'),
('Jaipur Textiles Co', 'contact@jaipurtextiles.in', '+91-141-2345678', 'Bapu Bazaar, Jaipur, Rajasthan'),
('Banaras Silk House', 'info@banarassilk.in', '+91-542-2345678', 'Vishwanath Gali, Varanasi, Uttar Pradesh'),
('Mumbai Cotton Mills', 'sales@mumbaicotton.in', '+91-22-23456789', 'Lower Parel, Mumbai, Maharashtra');

-- Insert Fabrics
INSERT INTO Fabrics (material, supplier_id, cost_per_meter) VALUES
('Banarasi Silk', 4, 2500.00),
('Kanchipuram Silk', 2, 3200.00),
('Cotton Khadi', 5, 450.00),
('Chanderi', 3, 1200.00),
('Georgette', 1, 380.00),
('Pashmina', 3, 4500.00),
('Raw Silk', 1, 850.00),
('Bandhani Fabric', 3, 650.00);

-- Insert Clothing Items
INSERT INTO Clothing_Items (name, size, color, price, collection_id) VALUES
('Designer Saree', 'Free Size', 'Royal Blue', 8999.00, 1),
('Embroidered Lehenga', 'M', 'Red & Gold', 25999.00, 5),
('Silk Kurta Set', 'L', 'Cream', 4999.00, 3),
('Sherwani', 'XL', 'Maroon', 18999.00, 4),
('Anarkali Suit', 'M', 'Pink', 6999.00, 1),
('Banarasi Dupatta', 'Free Size', 'Gold', 3499.00, 2),
('Indo-Western Gown', 'L', 'Emerald Green', 12999.00, 3),
('Pashmina Shawl', 'Free Size', 'Ivory', 15999.00, 4);

-- Insert Stores
INSERT INTO Stores (name, location, manager) VALUES
('Fashion Hub Delhi', 'Connaught Place, New Delhi, Delhi', 'Rajesh Verma'),
('Style Boutique Mumbai', 'Linking Road, Bandra, Mumbai, Maharashtra', 'Meera Iyer'),
('Trendy Store Bangalore', 'MG Road, Bangalore, Karnataka', 'Karthik Rao'),
('Urban Outlet Chennai', 'T Nagar, Chennai, Tamil Nadu', 'Lakshmi Nair'),
('Chic Gallery Hyderabad', 'Banjara Hills, Hyderabad, Telangana', 'Sanjay Reddy');

-- Insert Inventory
INSERT INTO Inventory (item_id, quantity_in_stock, reorder_level) VALUES
(1, 45, 10),
(2, 32, 15),
(3, 28, 10),
(4, 18, 5),
(5, 55, 20),
(6, 22, 8),
(7, 38, 12),
(8, 15, 5);

-- Insert Sales
INSERT INTO Sales (sale_date, store_id, item_id, quantity_sold, total_amount, payment) VALUES
('2024-10-01', 1, 1, 2, 17998.00, 'Credit Card'),
('2024-10-02', 2, 2, 1, 25999.00, 'UPI'),
('2024-10-03', 3, 5, 1, 6999.00, 'Debit Card'),
('2024-10-04', 1, 6, 2, 6998.00, 'Credit Card'),
('2024-10-05', 4, 4, 1, 18999.00, 'Net Banking'),
('2024-10-06', 5, 7, 1, 12999.00, 'UPI'),
('2024-10-07', 2, 3, 2, 9998.00, 'Cash'),
('2024-10-08', 3, 8, 1, 15999.00, 'Credit Card');

-- Insert into Supplies (Supplier-Fabric relationships)
INSERT INTO Supplies (supplier_id, fabric_id) VALUES
(4, 1), -- Banaras Silk House supplies Banarasi Silk
(2, 2), -- Kanchipuram Handlooms supplies Kanchipuram Silk
(5, 3), -- Mumbai Cotton Mills supplies Cotton Khadi
(3, 4), -- Jaipur Textiles supplies Chanderi
(1, 5), -- Surat Silk Mills supplies Georgette
(3, 6), -- Jaipur Textiles supplies Pashmina
(1, 7), -- Surat Silk Mills supplies Raw Silk
(3, 8); -- Jaipur Textiles supplies Bandhani Fabric

-- Insert into Uses (Fabric-Clothing Item relationships)
INSERT INTO Uses (fabric_id, item_id) VALUES
(1, 1), -- Banarasi Silk for Designer Saree
(2, 2), -- Kanchipuram Silk for Lehenga
(7, 3), -- Raw Silk for Kurta Set
(1, 4), -- Banarasi Silk for Sherwani
(5, 5), -- Georgette for Anarkali Suit
(1, 6), -- Banarasi Silk for Dupatta
(4, 7), -- Chanderi for Indo-Western Gown
(6, 8); -- Pashmina for Shawl

-- Insert into Clothing_Item_Fabrics (with quantities)
INSERT INTO Clothing_Item_Fabrics (item_id, fabric_id, quantity_used) VALUES
(1, 1, 6.0),  -- Designer Saree uses 6m Banarasi Silk
(2, 2, 8.5),  -- Lehenga uses 8.5m Kanchipuram Silk
(3, 7, 3.5),  -- Kurta Set uses 3.5m Raw Silk
(4, 1, 4.5),  -- Sherwani uses 4.5m Banarasi Silk
(5, 5, 4.0),  -- Anarkali uses 4m Georgette
(6, 1, 2.5),  -- Dupatta uses 2.5m Banarasi Silk
(7, 4, 5.0),  -- Gown uses 5m Chanderi
(8, 6, 2.0);  -- Shawl uses 2m Pashmina

-- Insert into Contains (Collection-Item relationships)
INSERT INTO Contains (collection_id, item_id) VALUES
(1, 1), -- Festive Splendor contains Designer Saree
(1, 5), -- Festive Splendor contains Anarkali Suit
(2, 6), -- Heritage Weaves contains Banarasi Dupatta
(3, 3), -- Modern Sarees contains Silk Kurta Set
(3, 7), -- Modern Sarees contains Indo-Western Gown
(4, 4), -- Royal Sherwanis contains Sherwani
(4, 8), -- Royal Sherwanis contains Pashmina Shawl
(5, 2); -- Bridal Dreams contains Embroidered Lehenga

-- Insert into Tracked_By (Item-Inventory relationships)
INSERT INTO Tracked_By (item_id, inventory_id) VALUES
(1, 1),
(2, 2),
(3, 3),
(4, 4),
(5, 5),
(6, 6),
(7, 7),
(8, 8);

-- Insert into Occurs_At (Sale-Store relationships)
INSERT INTO Occurs_At (sale_id, store_id) VALUES
(1, 1),
(2, 2),
(3, 3),
(4, 1),
(5, 4),
(6, 5),
(7, 2),
(8, 3);

-- Insert into Sold_In (Item-Sale relationships)  <-- CORRECTED alignment with Sales above
INSERT INTO Sold_In (item_id, sale_id) VALUES
(1, 1),
(2, 2),
(5, 3),
(6, 4),
(4, 5),
(7, 6),
(3, 7),
(8, 8);

-- Insert into Creates (Designer-Collection relationships)
INSERT INTO Creates (designer_id, collection_id) VALUES
(1, 1), -- Ananya creates Festive Splendor
(2, 2), -- Ravi creates Heritage Weaves
(3, 3), -- Priya creates Modern Sarees
(4, 4), -- Arjun creates Royal Sherwanis
(5, 5); -- Neha creates Bridal Dreams

-- ============================================================================
-- POST-SCHEMA CONSTRAINTS / INDEXES (minimal / non-drastic)
-- - Add UNIQUE constraint on Inventory(item_id) to ensure a single inventory row per item.
-- - Add helpful indexes for join performance.
-- ============================================================================

-- NOTE: If duplicates exist for Inventory(item_id) this ALTER will fail. Reconcile duplicates first.
ALTER TABLE Inventory
  ADD CONSTRAINT uq_inventory_item UNIQUE (item_id);

-- Helpful indexes (no semantic change)
CREATE INDEX IF NOT EXISTS idx_ci_collection_id ON Clothing_Items(collection_id);
CREATE INDEX IF NOT EXISTS idx_fabrics_supplier_id ON Fabrics(supplier_id);
CREATE INDEX IF NOT EXISTS idx_inv_item_id ON Inventory(item_id);
CREATE INDEX IF NOT EXISTS idx_cif_item_fabric ON Clothing_Item_Fabrics(item_id, fabric_id);
