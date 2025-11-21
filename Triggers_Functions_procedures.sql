-- ============================================================================
-- Fashion Business Queries, Triggers, Procedures & Functions (corrected)
-- - Minimal corrections only:
--   * Replaced risky triggers / ProcessSale with hardened versions.
--   * Added FK for Inventory_Alerts (Inventory_Alerts table retained; FK added).
-- ============================================================================

-- ============================================================================
-- TRIGGERS (replaced / hardened)
-- ============================================================================

-- If old triggers/procedures exist with these names, drop them first to avoid double behavior
DROP TRIGGER IF EXISTS before_sales_insert_check_stock;
DROP TRIGGER IF EXISTS after_sale_insert;
DROP TRIGGER IF EXISTS check_reorder_level;
DROP TRIGGER IF EXISTS prevent_designer_delete;
DROP PROCEDURE IF EXISTS ProcessSale;

DELIMITER $$

-- BEFORE INSERT trigger: check inventory exists & sufficient
CREATE TRIGGER before_sales_insert_check_stock
BEFORE INSERT ON Sales
FOR EACH ROW
BEGIN
  DECLARE v_stock INT;

  -- Check inventory exists for the item
  SELECT quantity_in_stock INTO v_stock FROM Inventory WHERE item_id = NEW.item_id;
  IF v_stock IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot insert Sale: no inventory record for this item';
  END IF;

  -- Check sufficient stock
  IF v_stock < NEW.quantity_sold THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot insert Sale: insufficient stock for this item';
  END IF;
END$$

-- AFTER INSERT trigger: decrement inventory by NEW.quantity_sold
CREATE TRIGGER after_sale_insert
AFTER INSERT ON Sales
FOR EACH ROW
BEGIN
  -- Safety check: Inventory row must exist (should be guaranteed by BEFORE trigger)
  UPDATE Inventory
    SET quantity_in_stock = quantity_in_stock - NEW.quantity_sold
    WHERE item_id = NEW.item_id;
END$$

-- Trigger: Check inventory reorder level and log into Inventory_Alerts table
-- Ensure Inventory_Alerts table exists (it will be created below if not present)
CREATE TABLE IF NOT EXISTS Inventory_Alerts (
    alert_id INT PRIMARY KEY AUTO_INCREMENT,
    item_id INT,
    message VARCHAR(255),
    alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- add a foreign key on Inventory_Alerts.item_id -> Clothing_Items(item_id)
-- (This enforces referential integrity for alerts)
-- If Inventory_Alerts already exists and FK doesn't, this will add it.
ALTER TABLE Inventory_Alerts
  ADD CONSTRAINT IF NOT EXISTS fk_inventoryalerts_item
    FOREIGN KEY (item_id) REFERENCES Clothing_Items(item_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE$$

-- After update on Inventory, insert alert when stock at/below reorder level
CREATE TRIGGER check_reorder_level
AFTER UPDATE ON Inventory
FOR EACH ROW
BEGIN
    IF NEW.quantity_in_stock <= NEW.reorder_level THEN
        INSERT INTO Inventory_Alerts (item_id, message)
        VALUES (NEW.item_id, CONCAT('Low stock alert: Only ', NEW.quantity_in_stock, ' items remaining'));
    END IF;
END$$

-- Prevent deletion of designers who have collections
CREATE TRIGGER prevent_designer_delete
BEFORE DELETE ON Designers
FOR EACH ROW
BEGIN
    DECLARE collection_count INT;
    SELECT COUNT(*) INTO collection_count
    FROM Collections
    WHERE designer_id = OLD.designer_id;

    IF collection_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot delete designer with existing collections';
    END IF;
END$$

DELIMITER ;

-- ============================================================================
-- STORED PROCEDURES (replaced / hardened)
-- ============================================================================

DELIMITER $$

-- Transactional ProcessSale:
-- - checks and locks inventory (SELECT ... FOR UPDATE)
-- - inserts into Sales (BEFORE trigger will re-check stock)
-- - inserts into Occurs_At and Sold_In
-- - commits; inventory decrement handled by AFTER INSERT trigger
CREATE PROCEDURE ProcessSale(
  IN p_item_id INT,
  IN p_store_id INT,
  IN p_quantity INT,
  IN p_payment_method VARCHAR(50)
)
BEGIN
  DECLARE v_price DECIMAL(10,2);
  DECLARE v_total DECIMAL(12,2);
  DECLARE v_sale_id BIGINT;

  -- Start transaction to make operation atomic
  START TRANSACTION;

  -- Lock the related Clothing_Items/Inventory row for update to avoid race conditions
  SELECT ci.price
    INTO v_price
    FROM Clothing_Items ci
    JOIN Inventory i ON i.item_id = ci.item_id
    WHERE ci.item_id = p_item_id
    FOR UPDATE;

  IF v_price IS NULL THEN
    ROLLBACK;
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ProcessSale: item not found or no inventory record';
  END IF;

  SET v_total = p_quantity * v_price;

  -- Insert into Sales (BEFORE trigger will verify stock)
  INSERT INTO Sales (sale_date, quantity_sold, total_amount, item_id, store_id, payment)
  VALUES (NOW(), p_quantity, v_total, p_item_id, p_store_id, p_payment_method);

  SET v_sale_id = LAST_INSERT_ID();

  -- Keep Occurs_At and Sold_In consistent with Sales table
  INSERT INTO Occurs_At (sale_id, store_id) VALUES (v_sale_id, p_store_id);
  INSERT INTO Sold_In (item_id, sale_id) VALUES (p_item_id, v_sale_id);

  COMMIT;
END$$

DELIMITER ;

-- ============================================================================
-- OTHER PROCEDURES (kept original functionality; no change except formatting)
-- ============================================================================

DELIMITER //
CREATE PROCEDURE GetDesignerPortfolio(IN p_designer_id INT)
BEGIN
    -- Designer info
    SELECT * FROM Designers WHERE designer_id = p_designer_id;

    -- Collections
    SELECT * FROM Collections WHERE designer_id = p_designer_id;

    -- Items in collections
    SELECT ci.*, c.name AS collection_name
    FROM Clothing_Items ci
    JOIN Collections c ON ci.collection_id = c.collection_id
    WHERE c.designer_id = p_designer_id;
END//
DELIMITER ;

DELIMITER //
CREATE PROCEDURE MonthlySalesReport(
    IN p_store_id INT,
    IN p_month INT,
    IN p_year INT
)
BEGIN
    SELECT 
        s.store_id,
        st.name AS store_name,
        COUNT(s.sale_id) AS total_transactions,
        SUM(s.quantity_sold) AS total_items_sold,
        SUM(s.total_amount) AS total_revenue,
        AVG(s.total_amount) AS avg_transaction_value
    FROM Sales s
    JOIN Stores st ON s.store_id = st.store_id
    WHERE s.store_id = p_store_id
        AND MONTH(s.sale_date) = p_month
        AND YEAR(s.sale_date) = p_year
    GROUP BY s.store_id, st.name;
END//
DELIMITER ;

-- ============================================================================
-- FUNCTIONS (kept original functions)
-- ============================================================================

DELIMITER //
CREATE FUNCTION GetItemFabricCost(p_item_id INT)
RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
    DECLARE total_cost DECIMAL(10,2);

    SELECT SUM(cif.quantity_used * f.cost_per_meter)
    INTO total_cost
    FROM Clothing_Item_Fabrics cif
    JOIN Fabrics f ON cif.fabric_id = f.fabric_id
    WHERE cif.item_id = p_item_id;

    RETURN IFNULL(total_cost, 0);
END//
DELIMITER ;

DELIMITER //
CREATE FUNCTION GetProfitMargin(p_item_id INT)
RETURNS DECIMAL(5,2)
DETERMINISTIC
BEGIN
    DECLARE item_price DECIMAL(10,2);
    DECLARE fabric_cost DECIMAL(10,2);
    DECLARE profit_margin DECIMAL(5,2);

    SELECT price INTO item_price
    FROM Clothing_Items
    WHERE item_id = p_item_id;

    SET fabric_cost = GetItemFabricCost(p_item_id);

    IF item_price > 0 THEN
        SET profit_margin = ((item_price - fabric_cost) / item_price) * 100;
    ELSE
        SET profit_margin = 0;
    END IF;

    RETURN profit_margin;
END//
DELIMITER ;

DELIMITER //
CREATE FUNCTION GetDesignerRevenue(p_designer_id INT)
RETURNS DECIMAL(12,2)
DETERMINISTIC
BEGIN
    DECLARE total_revenue DECIMAL(12,2);

    SELECT SUM(s.total_amount)
    INTO total_revenue
    FROM Sales s
    JOIN Clothing_Items ci ON s.item_id = ci.item_id
    JOIN Collections c ON ci.collection_id = c.collection_id
    WHERE c.designer_id = p_designer_id;

    RETURN IFNULL(total_revenue, 0);
END//
DELIMITER ;

-- ============================================================================
-- NESTED QUERIES, JOIN QUERIES, AGGREGATE QUERIES (kept original queries mostly)
-- ============================================================================

-- ============================================================================
-- NESTED QUERIES
-- ============================================================================

-- Nested Query 1: Find items more expensive than average price in their collection
SELECT 
    ci.item_id,
    ci.name,
    ci.price,
    c.name AS collection_name
FROM Clothing_Items ci
JOIN Collections c ON ci.collection_id = c.collection_id
WHERE ci.price > (
    SELECT AVG(ci2.price)
    FROM Clothing_Items ci2
    WHERE ci2.collection_id = ci.collection_id
)
ORDER BY c.name, ci.price DESC;

-- Nested Query 2: Find designers whose collections have generated above-average revenue
SELECT 
    d.designer_id,
    d.name,
    d.style,
    (SELECT SUM(s.total_amount)
     FROM Sales s
     JOIN Clothing_Items ci ON s.item_id = ci.item_id
     JOIN Collections c ON ci.collection_id = c.collection_id
     WHERE c.designer_id = d.designer_id) AS total_revenue
FROM Designers d
WHERE (
    SELECT SUM(s.total_amount)
    FROM Sales s
    JOIN Clothing_Items ci ON s.item_id = ci.item_id
    JOIN Collections c ON ci.collection_id = c.collection_id
    WHERE c.designer_id = d.designer_id
) > (
    SELECT AVG(designer_revenue)
    FROM (
        SELECT SUM(s.total_amount) AS designer_revenue
        FROM Sales s
        JOIN Clothing_Items ci ON s.item_id = ci.item_id
        JOIN Collections c ON ci.collection_id = c.collection_id
        GROUP BY c.designer_id
    ) AS revenue_table
)
ORDER BY total_revenue DESC;

-- Nested Query 3: Find items that use the most expensive fabrics
SELECT 
    ci.item_id,
    ci.name,
    ci.price,
    (SELECT f.material
     FROM Fabrics f
     JOIN Uses u ON f.fabric_id = u.fabric_id
     WHERE u.item_id = ci.item_id
     ORDER BY f.cost_per_meter DESC
     LIMIT 1) AS most_expensive_fabric,
    (SELECT MAX(f.cost_per_meter)
     FROM Fabrics f
     JOIN Uses u ON f.fabric_id = u.fabric_id
     WHERE u.item_id = ci.item_id) AS max_fabric_cost
FROM Clothing_Items ci
WHERE ci.item_id IN (
    SELECT u.item_id
    FROM Uses u
    JOIN Fabrics f ON u.fabric_id = f.fabric_id
    WHERE f.cost_per_meter > 2000
)
ORDER BY max_fabric_cost DESC;

-- ============================================================================
-- JOIN QUERIES (examples)
-- ============================================================================

-- Join Query 1: Complete Product Information with Designer and Supplier Details
SELECT 
    ci.item_id,
    ci.name AS item_name,
    ci.price,
    ci.size,
    ci.color,
    c.name AS collection_name,
    d.name AS designer_name,
    d.style AS designer_style,
    f.material AS fabric_type,
    f.cost_per_meter AS fabric_cost,
    s.name AS supplier_name,
    s.address AS supplier_location
FROM Clothing_Items ci
INNER JOIN Collections c ON ci.collection_id = c.collection_id
INNER JOIN Designers d ON c.designer_id = d.designer_id
INNER JOIN Uses u ON ci.item_id = u.item_id
INNER JOIN Fabrics f ON u.fabric_id = f.fabric_id
INNER JOIN Suppliers s ON f.supplier_id = s.supplier_id
ORDER BY ci.item_id;

-- Join Query 2: Sales Performance by Store with Item Details
SELECT 
    st.store_id,
    st.name AS store_name,
    st.location,
    ci.name AS item_name,
    COUNT(s.sale_id) AS number_of_sales,
    SUM(s.quantity_sold) AS total_quantity,
    SUM(s.total_amount) AS total_revenue
FROM Stores st
INNER JOIN Sales s ON st.store_id = s.store_id
INNER JOIN Clothing_Items ci ON s.item_id = ci.item_id
GROUP BY st.store_id, st.name, st.location, ci.name
ORDER BY total_revenue DESC;

-- Join Query 3: Inventory Status with Low Stock Items
SELECT 
    ci.item_id,
    ci.name AS item_name,
    ci.price,
    i.quantity_in_stock,
    i.reorder_level,
    CASE 
        WHEN i.quantity_in_stock <= i.reorder_level THEN 'Low Stock - Reorder Now'
        WHEN i.quantity_in_stock <= (i.reorder_level * 2) THEN 'Warning - Stock Running Low'
        ELSE 'Stock OK'
    END AS stock_status,
    f.material AS fabric_needed,
    s.name AS supplier_name,
    s.phone AS supplier_contact
FROM Inventory i
INNER JOIN Clothing_Items ci ON i.item_id = ci.item_id
INNER JOIN Uses u ON ci.item_id = u.item_id
INNER JOIN Fabrics f ON u.fabric_id = f.fabric_id
INNER JOIN Suppliers s ON f.supplier_id = s.supplier_id
ORDER BY i.quantity_in_stock ASC;

-- Join Query 4: Designer Performance Analysis
SELECT 
    d.designer_id,
    d.name AS designer_name,
    d.style,
    COUNT(DISTINCT c.collection_id) AS total_collections,
    COUNT(DISTINCT ci.item_id) AS total_items_designed,
    COUNT(DISTINCT s.sale_id) AS total_sales,
    IFNULL(SUM(s.total_amount), 0) AS total_revenue_generated
FROM Designers d
LEFT JOIN Collections c ON d.designer_id = c.designer_id
LEFT JOIN Clothing_Items ci ON c.collection_id = ci.collection_id
LEFT JOIN Sales s ON ci.item_id = s.item_id
GROUP BY d.designer_id, d.name, d.style
ORDER BY total_revenue_generated DESC;

-- ============================================================================
-- AGGREGATE QUERIES
-- ============================================================================

-- Aggregate Query 1: Sales Summary by Payment Method
SELECT 
    payment,
    COUNT(*) AS transaction_count,
    SUM(quantity_sold) AS total_items_sold,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount) AS avg_transaction_value,
    MIN(total_amount) AS min_transaction,
    MAX(total_amount) AS max_transaction
FROM Sales
GROUP BY payment
ORDER BY total_revenue DESC;

-- Aggregate Query 2: Collection Performance Analysis
SELECT 
    c.collection_id,
    c.name AS collection_name,
    c.season,
    c.year,
    d.name AS designer_name,
    COUNT(ci.item_id) AS items_in_collection,
    AVG(ci.price) AS avg_item_price,
    MIN(ci.price) AS min_price,
    MAX(ci.price) AS max_price,
    IFNULL(SUM(s.total_amount), 0) AS total_sales_revenue,
    IFNULL(SUM(s.quantity_sold), 0) AS total_items_sold
FROM Collections c
INNER JOIN Designers d ON c.designer_id = d.designer_id
LEFT JOIN Clothing_Items ci ON c.collection_id = ci.collection_id
LEFT JOIN Sales s ON ci.item_id = s.item_id
GROUP BY c.collection_id, c.name, c.season, c.year, d.name
ORDER BY total_sales_revenue DESC;

-- Aggregate Query 3: Fabric Usage and Cost Analysis
SELECT 
    f.fabric_id,
    f.material,
    f.cost_per_meter,
    s.name AS supplier_name,
    COUNT(DISTINCT cif.item_id) AS items_using_fabric,
    SUM(cif.quantity_used) AS total_meters_used,
    SUM(cif.quantity_used * f.cost_per_meter) AS total_fabric_cost,
    AVG(cif.quantity_used) AS avg_meters_per_item
FROM Fabrics f
INNER JOIN Suppliers s ON f.supplier_id = s.supplier_id
LEFT JOIN Clothing_Item_Fabrics cif ON f.fabric_id = cif.fabric_id
GROUP BY f.fabric_id, f.material, f.cost_per_meter, s.name
ORDER BY total_fabric_cost DESC;

-- Aggregate Query 4: Store Performance Comparison
SELECT 
    st.store_id,
    st.name AS store_name,
    st.location,
    st.manager,
    COUNT(DISTINCT s.sale_id) AS total_transactions,
    COUNT(DISTINCT s.item_id) AS unique_items_sold,
    SUM(s.quantity_sold) AS total_items_sold,
    SUM(s.total_amount) AS total_revenue,
    AVG(s.total_amount) AS avg_transaction_value,
    MAX(s.total_amount) AS highest_sale
FROM Stores st
LEFT JOIN Sales s ON st.store_id = s.store_id
GROUP BY st.store_id, st.name, st.location, st.manager
ORDER BY total_revenue DESC;

-- Aggregate Query 5: Monthly Revenue Trend
SELECT 
    YEAR(sale_date) AS year,
    MONTH(sale_date) AS month,
    MONTHNAME(sale_date) AS month_name,
    COUNT(sale_id) AS total_transactions,
    SUM(quantity_sold) AS items_sold,
    SUM(total_amount) AS monthly_revenue,
    AVG(total_amount) AS avg_sale_value
FROM Sales
GROUP BY YEAR(sale_date), MONTH(sale_date), MONTHNAME(sale_date)
ORDER BY year DESC, month DESC;

-- Aggregate Query 6: Top Selling Items
SELECT 
    ci.item_id,
    ci.name AS item_name,
    ci.price,
    c.name AS collection_name,
    d.name AS designer_name,
    COUNT(s.sale_id) AS times_sold,
    SUM(s.quantity_sold) AS total_quantity_sold,
    SUM(s.total_amount) AS total_revenue,
    AVG(s.total_amount) AS avg_sale_value
FROM Clothing_Items ci
INNER JOIN Collections c ON ci.collection_id = c.collection_id
INNER JOIN Designers d ON c.designer_id = d.designer_id
LEFT JOIN Sales s ON ci.item_id = s.item_id
GROUP BY ci.item_id, ci.name, ci.price, c.name, d.name
HAVING times_sold > 0
ORDER BY total_revenue DESC
LIMIT 10;

-- ============================================================================
-- USAGE EXAMPLES
-- ============================================================================

-- Example: CALL ProcessSale for item 1 at store 1, 2 units, payment 'UPI'
-- CALL ProcessSale(1, 1, 2, 'UPI');

-- Example: Check fabric cost for item
-- SELECT item_id, name, GetItemFabricCost(item_id) AS fabric_cost FROM Clothing_Items;

-- Example: Get profit margin for an item
-- SELECT item_id, name, GetProfitMargin(item_id) AS profit_margin FROM Clothing_Items;

-- Example: Designer revenue
-- SELECT designer_id, name, GetDesignerRevenue(designer_id) AS revenue FROM Designers;
