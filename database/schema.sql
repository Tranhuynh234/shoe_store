
CREATE DATABASE IF NOT EXISTS giaytuan CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE giaytuan;

CREATE TABLE users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  full_name     VARCHAR(120) NOT NULL,
  email         VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,             -- chỉ lưu hash (Werkzeug), không lưu mật khẩu gốc
  phone         VARCHAR(20) NULL,
  role          VARCHAR(20) NOT NULL DEFAULT 'CUSTOMER',
  is_active     TINYINT(1) NOT NULL DEFAULT 1,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_users_email (email),
  CONSTRAINT ck_users_role CHECK (role IN ('CUSTOMER','ADMIN'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE addresses (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  user_id        INT NOT NULL,
  recipient_name VARCHAR(120) NOT NULL,
  phone          VARCHAR(20) NOT NULL,
  province       VARCHAR(100) NOT NULL,
  district       VARCHAR(100) NOT NULL,
  ward           VARCHAR(100) NOT NULL,
  address_detail VARCHAR(255) NOT NULL,
  is_default     TINYINT(1) NOT NULL DEFAULT 0,
  KEY ix_addresses_user (user_id),
  CONSTRAINT fk_addresses_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE categories (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(100) NOT NULL,
  slug        VARCHAR(120) NOT NULL,
  description TEXT NULL,
  is_active   TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_categories_name (name),
  UNIQUE KEY uq_categories_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE brands (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(100) NOT NULL,
  slug        VARCHAR(120) NOT NULL,
  description TEXT NULL,
  logo        VARCHAR(255) NULL,                   -- đường dẫn tương đối trong static/
  cover_image VARCHAR(255) NULL,                   -- ảnh đại diện ở trang chủ (bổ sung)
  UNIQUE KEY uq_brands_name (name),
  UNIQUE KEY uq_brands_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE products (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  category_id  INT NOT NULL,
  brand_id     INT NULL,
  name         VARCHAR(200) NOT NULL,
  slug         VARCHAR(220) NOT NULL,
  product_code VARCHAR(50) NOT NULL,
  description  TEXT NULL,
  material     VARCHAR(255) NULL,
  origin       VARCHAR(100) NULL,
  price        DECIMAL(12,0) NOT NULL,
  sale_price   DECIMAL(12,0) NULL,
  is_active    TINYINT(1) NOT NULL DEFAULT 1,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_products_slug (slug),
  UNIQUE KEY uq_products_code (product_code),
  KEY ix_products_name (name),
  KEY ix_products_active_category_brand (is_active, category_id, brand_id),
  CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
  CONSTRAINT fk_products_brand    FOREIGN KEY (brand_id)    REFERENCES brands(id)     ON DELETE RESTRICT,
  CONSTRAINT ck_products_price      CHECK (price >= 0),
  CONSTRAINT ck_products_sale_price CHECK (sale_price IS NULL OR (sale_price >= 0 AND sale_price <= price))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_images (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  product_id INT NOT NULL,
  image_url  VARCHAR(255) NOT NULL,                -- đường dẫn tương đối trong static/
  is_primary TINYINT(1) NOT NULL DEFAULT 0,
  sort_order INT NOT NULL DEFAULT 0,
  KEY ix_product_images_product (product_id),
  CONSTRAINT fk_product_images_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_variants (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  product_id     INT NOT NULL,
  size           VARCHAR(20) NOT NULL,
  color          VARCHAR(50) NOT NULL DEFAULT '',  -- '' = màu mặc định (tránh NULL làm hỏng UNIQUE)
  sku            VARCHAR(80) NOT NULL,
  stock_quantity INT NOT NULL DEFAULT 0,
  UNIQUE KEY uq_variants_sku (sku),
  UNIQUE KEY uq_variant_product_size_color (product_id, size, color),
  CONSTRAINT fk_variants_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  CONSTRAINT ck_variants_stock CHECK (stock_quantity >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE carts (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_carts_user (user_id),
  CONSTRAINT fk_carts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE cart_items (
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  cart_id            INT NOT NULL,
  product_variant_id INT NOT NULL,
  quantity           INT NOT NULL DEFAULT 1,
  UNIQUE KEY uq_cart_variant (cart_id, product_variant_id),
  CONSTRAINT fk_cart_items_cart    FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
  CONSTRAINT fk_cart_items_variant FOREIGN KEY (product_variant_id) REFERENCES product_variants(id) ON DELETE CASCADE,
  CONSTRAINT ck_cart_items_qty CHECK (quantity > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE orders (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  order_code      VARCHAR(32) NOT NULL,
  user_id         INT NOT NULL,
  address_id      INT NULL,
  ship_name       VARCHAR(120) NOT NULL,           -- snapshot địa chỉ giao hàng
  ship_phone      VARCHAR(20) NOT NULL,
  ship_address    VARCHAR(500) NOT NULL,
  subtotal        DECIMAL(12,0) NOT NULL,
  shipping_fee    DECIMAL(12,0) NOT NULL DEFAULT 0,
  discount_amount DECIMAL(12,0) NOT NULL DEFAULT 0,
  total_amount    DECIMAL(12,0) NOT NULL,
  payment_method  VARCHAR(20) NOT NULL DEFAULT 'COD',
  payment_status  VARCHAR(20) NOT NULL DEFAULT 'UNPAID',   -- tách riêng khỏi order_status
  order_status    VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  customer_note   VARCHAR(500) NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_orders_code (order_code),
  KEY ix_orders_status (order_status),
  KEY ix_orders_user_created (user_id, created_at),
  CONSTRAINT fk_orders_user    FOREIGN KEY (user_id)    REFERENCES users(id)     ON DELETE RESTRICT,
  CONSTRAINT fk_orders_address FOREIGN KEY (address_id) REFERENCES addresses(id) ON DELETE SET NULL,
  CONSTRAINT ck_orders_amounts CHECK (subtotal >= 0 AND shipping_fee >= 0 AND discount_amount >= 0 AND total_amount >= 0),
  CONSTRAINT ck_orders_status  CHECK (order_status IN ('PENDING','CONFIRMED','SHIPPING','COMPLETED','CANCELLED')),
  CONSTRAINT ck_orders_pay_status CHECK (payment_status IN ('UNPAID','PAID','FAILED','REFUNDED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE order_items (
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  order_id           INT NOT NULL,
  product_variant_id INT NULL,
  product_id         INT NULL,
  product_name       VARCHAR(200) NOT NULL,        -- snapshot tại thời điểm mua
  product_code       VARCHAR(50) NOT NULL,
  size               VARCHAR(20) NOT NULL,
  color              VARCHAR(50) NOT NULL DEFAULT '',
  unit_price         DECIMAL(12,0) NOT NULL,
  quantity           INT NOT NULL,
  subtotal           DECIMAL(12,0) NOT NULL,
  KEY ix_order_items_order (order_id),
  KEY ix_order_items_product (product_id),
  CONSTRAINT fk_order_items_order   FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_order_items_variant FOREIGN KEY (product_variant_id) REFERENCES product_variants(id) ON DELETE SET NULL,
  CONSTRAINT fk_order_items_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
  CONSTRAINT ck_order_items_values CHECK (quantity > 0 AND unit_price >= 0 AND subtotal >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE payments (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  order_id          INT NOT NULL,
  payment_method    VARCHAR(20) NOT NULL,
  amount            DECIMAL(12,0) NOT NULL,
  transaction_code  VARCHAR(100) NULL,             -- chỉ nhập khi đã xác minh; hệ thống không tự sinh
  payment_status    VARCHAR(20) NOT NULL DEFAULT 'UNPAID',
  verification_note VARCHAR(500) NULL,
  paid_at           DATETIME NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_payments_order (order_id),
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT ck_payments_amount CHECK (amount >= 0),
  CONSTRAINT ck_payments_status CHECK (payment_status IN ('UNPAID','PAID','FAILED','REFUNDED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE reviews (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,
  product_id    INT NOT NULL,
  order_item_id INT NULL,
  rating        INT NOT NULL,
  comment       TEXT NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_reviews_order_item (order_item_id),
  KEY ix_reviews_user (user_id),
  KEY ix_reviews_product (product_id),
  CONSTRAINT fk_reviews_user    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_reviews_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  CONSTRAINT fk_reviews_item    FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE SET NULL,
  CONSTRAINT ck_reviews_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE blog_posts (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  title        VARCHAR(200) NOT NULL,
  slug         VARCHAR(220) NOT NULL,
  summary      VARCHAR(500) NULL,
  content      LONGTEXT NOT NULL,
  thumbnail    VARCHAR(255) NULL,
  status       VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
  published_at DATETIME NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_blog_slug (slug),
  KEY ix_blog_status_published (status, published_at),
  CONSTRAINT ck_blog_status CHECK (status IN ('DRAFT','PUBLISHED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE contact_messages (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  full_name  VARCHAR(120) NOT NULL,
  email      VARCHAR(255) NOT NULL,
  phone      VARCHAR(20) NULL,
  subject    VARCHAR(200) NOT NULL,
  message    TEXT NOT NULL,
  status     VARCHAR(20) NOT NULL DEFAULT 'NEW',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_contact_status (status),
  CONSTRAINT ck_contact_status CHECK (status IN ('NEW','READ','RESOLVED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE rate_limit_events (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  bucket     VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_rate_limit_bucket_time (bucket, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;