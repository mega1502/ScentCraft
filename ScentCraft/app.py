import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import random # احتاجه عشان السيد داتا
from flask import jsonify
import google.generativeai as genai
import os

# هنا بتحط مفتاحك اللي هتجيبه من Google AI Studio
# يفضل تحطه في متغيرات البيئة، بس للتجربة ممكن تحطه هنا
GENAI_API_KEY = "حط_المفتاح_بتاعك_هنا"
genai.configure(api_key=GENAI_API_KEY)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scentcraft.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
# ضيف السطر ده تحت إعدادات app.config
app.config['BOTTLE_PRICES'] = {'50': 350, '100': 500, '200': 800}

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    member_since = db.Column(db.DateTime, default=datetime.utcnow)
    profile_pic = db.Column(db.String(150), default='default_avatar.png')
    
    # --- التعديل الجديد: هل هو أدمن؟ ---
    is_admin = db.Column(db.Boolean, default=False)

    orders = db.relationship('Order', backref='user', lazy=True)
    wishlist = db.relationship('Wishlist', backref='user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    # الصورة والوصف بقوا أساسيين
    image = db.Column(db.String(500), default='https://via.placeholder.com/300') 
    desc = db.Column(db.Text)

# (باقي الجداول زي ما هي Wishlist, Order, OrderItem...)
class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product = db.relationship('Product')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Processing')
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    product_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    # --- العمود الجديد (الروشيتة) ---
    details = db.Column(db.String(500), nullable=True) # هيشيل تفاصيل زي: "Top: Mint (30%), Base: Oud (70%)"

# --- Ingredient Model (جدول مكونات المعمل) ---
class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False) # Top, Heart, Base
    price = db.Column(db.Float, nullable=False)
    color = db.Column(db.String(20), nullable=False) # Hex Code (e.g. #FF0000)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---
@app.route('/')
def home(): return render_template('index.html')

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    mode = request.args.get('mode', 'login')
    if request.method == 'POST':
        # --- حالة إنشاء حساب جديد (Sign Up) ---
        if 'signup_name' in request.form:
            name = request.form['signup_name']
            email = request.form['signup_email']
            password = request.form['signup_password']
            
            # التأكد إن الإيميل مش مستخدم قبل كده
            if User.query.filter_by(email=email).first():
                flash('Email already exists!', 'error')
                return redirect(url_for('login', mode='signup'))
            
            # --- التعديل هنا: أي مستخدم جديد هو "عميل" فقط ---
            # لغينا الكود اللي كان بيخليه أدمن لو اسمه زياد
            new_user = User(
                name=name, 
                email=email, 
                password=generate_password_hash(password, method='pbkdf2:sha256'),
                is_admin=False  # <--- دي أهم نقطة: صلاحية الأدمن مقفولة
            )
            
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('home'))

        # --- حالة تسجيل الدخول (Log In) ---
        else:
            email = request.form['login_email']
            password = request.form['login_password']
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                
                # توجيه ذكي: لو أدمن يروح لوحة التحكم، لو عميل يروح البروفايل
                # (اختياري: ممكن تخليه يروح البروفايل علطول زي ما تحب)
                return redirect(url_for('home'))
            else:
                flash('Invalid email or password', 'error')
                return redirect(url_for('login', mode='login'))
                
    return render_template('login.html', mode=mode)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/lab')
def lab():
    top_notes = Ingredient.query.filter_by(category='top').all()
    heart_notes = Ingredient.query.filter_by(category='heart').all()
    base_notes = Ingredient.query.filter_by(category='base').all()
    
    # بعتنا الأسعار هنا 👇
    return render_template('lab.html', top=top_notes, heart=heart_notes, base=base_notes, prices=app.config['BOTTLE_PRICES'])

@app.route('/shop')
def shop():
    products = Product.query.all()
    return render_template('shop.html', products=products)

@app.route('/product/<int:product_id>')
def product_details(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product.html', product=product)

@app.route('/profile')
@login_required
def profile():
    # 1. فلترة الأوردرات: هات كل الأوردرات ما عدا "Cancelled"
    valid_orders = [o for o in current_user.orders if o.status != 'Cancelled']
    
    # 2. حساب العدد والمجموع للأوردرات السليمة فقط
    orders_count = len(valid_orders)
    total_spent = sum(o.total for o in valid_orders)
    
    # 3. نبعت الأرقام دي للصفحة عشان تتعرض
    return render_template('profile.html', user=current_user, orders_count=orders_count, total_spent=total_spent)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not check_password_hash(current_user.password, current_password):
        flash('Incorrect current password!', 'error')
        return redirect(url_for('profile'))
    
    if new_password != confirm_password:
        flash('New passwords do not match!', 'error')
        return redirect(url_for('profile'))

    current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
    db.session.commit()
    flash('Password changed successfully!', 'success')
    return redirect(url_for('profile'))

@app.route('/toggle_wishlist/<int:product_id>')
@login_required
def toggle_wishlist(product_id):
    item = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        db.session.delete(item)
    else:
        new_item = Wishlist(user_id=current_user.id, product_id=product_id)
        db.session.add(new_item)
    db.session.commit()
    return redirect(request.referrer or url_for('shop'))

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    data = request.get_json() # استلام البيانات من الجافاسكريبت
    cart_items = data.get('items') # قائمة المنتجات
    
    if not cart_items:
        return jsonify({'status': 'error', 'message': 'Cart is empty'}), 400

    # 1. إنشاء الأوردر الأساسي
    new_order = Order(user_id=current_user.id, status="Processing", total=0)
    db.session.add(new_order)
    db.session.commit() # عشان ناخد ID للأوردر

    total_price = 0
    
    # 2. إضافة تفاصيل المنتجات وحساب السعر
    # ... جوه الـ loop بتاع cart_items ...
    for item in cart_items:
        price = float(str(item['price']).replace(' EGP', '').strip())
        qty = int(item['qty'])
        total_price += price * qty
        
        # بنستقبل التفاصيل (لو مفيش، بنحط شرطة -)
        item_details = item.get('details', '-') 
        
        order_item = OrderItem(
            order_id=new_order.id,
            product_name=item['name'],
            product_price=price,
            quantity=qty,
            details=item_details  # حفظنا الروشيتة هنا
        )
        db.session.add(order_item)
    # ... باقي الكود زي ما هو ...

    # 3. تحديث السعر النهائي للأوردر
    new_order.total = total_price
    db.session.commit()

    return jsonify({'status': 'success'})

@app.route('/order_action/<int:order_id>/<action>')
@login_required
def order_action(order_id, action):
    order = Order.query.get_or_404(order_id)
    
    # حماية: لازم الأوردر يكون بتاع المستخدم الحالي
    if order.user_id != current_user.id:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('profile'))
    
    # لو العميل عايز يلغي (والأوردر لسه قيد التجهيز)
    if action == 'cancel' and order.status == 'Processing':
        order.status = 'Cancelled'
        db.session.commit()
        flash('Order cancelled successfully.', 'info')
        
    # لو العميل عايز يأكد الاستلام (والأوردر مش ملغي)
    elif action == 'confirm' and order.status != 'Cancelled':
        order.status = 'Delivered'
        db.session.commit()
        flash('Order marked as received! Thank you.', 'success')
        
    return redirect(url_for('profile'))

# -----------------------------------------------
# --- منطقة الأدمن الجديدة (Admin Zone) ---
# -----------------------------------------------

# 1. عرض لوحة التحكم
@app.route('/admin')
@login_required
def admin_panel():
    # حماية: لو المستخدم مش أدمن، نرجعه للصفحة الرئيسية
    if not current_user.is_admin:
        flash('Access Denied! Admins only.', 'error')
        return redirect(url_for('home'))
    
    products = Product.query.all()
    return render_template('admin.html', products=products)

# 2. إضافة منتج جديد
# 2. إضافة منتج جديد (تم التعديل ليعود للمتجر)
import os
from werkzeug.utils import secure_filename

# 1. إعداد المسار الصحيح (ده الحل الجذري لمشكلة الصور)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')

# تأكد إن الفولدر موجود، ولو مش موجود اصنعه
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# ... (باقي الكود زي ما هو) ...

# 2. دالة إضافة المنتج (النسخة السليمة)
@app.route('/admin/add_product', methods=['POST'])
@login_required
def add_product():
    # حماية: لو مش أدمن، يرجع للهوم
    if not current_user.is_admin: 
        return redirect(url_for('home'))

    name = request.form['name']
    price = float(request.form['price'])
    category = request.form['category']
    desc = request.form['desc']
    
    # التعامل مع الصورة
    image_path = "https://via.placeholder.com/300" # صورة احتياطية
    
    if 'image' in request.files:
        file = request.files['image']
        if file.filename != '':
            filename = secure_filename(file.filename)
            # بنحفظ الصورة في المسار الكامل اللي حددناه فوق
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # بنسجل المسار النسبي عشان يظهر في الـ HTML
            image_path = url_for('static', filename='uploads/' + filename)

    # حفظ المنتج في الداتا بيز
    new_prod = Product(name=name, price=price, category=category, desc=desc, image=image_path)
    db.session.add(new_prod)
    db.session.commit()
    
    flash('Product added successfully!', 'success')
    return redirect(url_for('shop'))
# 3. حذف منتج (تم التعديل ليعود للمتجر)
@app.route('/admin/delete_product/<int:id>')
@login_required
def delete_product(id):
    if not current_user.is_admin: return redirect(url_for('home'))
    
    prod = Product.query.get_or_404(id)
    # قبل ما نمسح المنتج، نمسحه من الـ Wishlist والـ Cart عشان ميعملش مشاكل
    Wishlist.query.filter_by(product_id=id).delete()
    # (لو عندك جدول Cart في الداتا بيز امسحه منه، بس إحنا شغالين LocalStorage فتمام)
    
    db.session.delete(prod)
    db.session.commit()
    flash('Product deleted!', 'info')
    return redirect(url_for('shop')) # <--- التغيير هنا: بيرجع للمتجر

# --- Seed Data (لأول مرة بس) ---
# --- Seed Data (تجهيز البيانات + حساب الأدمن) ---
def seed_data():
    # 1. إنشاء حساب الأدمن الثابت (لو مش موجود)
    admin_email = "admin@scentcraft.com"
    if not User.query.filter_by(email=admin_email).first():
        admin_user = User(
            name="ScentCraft Manager",
            email=admin_email,
            password=generate_password_hash("123456", method='pbkdf2:sha256'), # ده الباسورد
            phone="01000000000",
            address="Headquarters",
            is_admin=True # صلاحية كاملة
        )
        db.session.add(admin_user)
        db.session.commit()
        print(">>> Admin Account Created Successfully! (admin@scentcraft.com / 123456)")

    # 2. إنشاء المنتجات (لو الداتا بيز فاضية)
    if Product.query.count() == 0:
        import random
        adjectives = ["Royal", "Midnight", "Golden", "Velvet", "Dark", "Ocean", "Mystic", "Pure", "Imperial", "Wild"]
        nouns = ["Oud", "Musk", "Rose", "Amber", "Breeze", "Wood", "Spice", "Jasmine", "Orchid", "Leather"]
        categories = ["Men", "Women", "Unisex"]
        
        # صور حقيقية متنوعة
        images = [
            "https://images.unsplash.com/photo-1594035910387-fea47794261f?w=600",
            "https://images.unsplash.com/photo-1523293182086-7651a899d37f?w=600",
            "https://images.unsplash.com/photo-1541643600914-78b084683601?w=600",
            "https://images.unsplash.com/photo-1592945403244-b3fbafd7f539?w=600",
            "https://images.unsplash.com/photo-1512777576244-b846ac3d816f?w=600",
            "https://images.unsplash.com/photo-1585232004114-187532386926?w=600"
        ]
        
        products_list = []
        for i in range(100):
            name = f"{random.choice(adjectives)} {random.choice(nouns)} {random.randint(10, 99)}"
            cat = random.choice(categories)
            price = random.randint(800, 5000)
            img = random.choice(images)
            desc = f"A unique {cat.lower()} fragrance with notes of {name.split()[1]} and nature's finest essences."
            
            p = Product(name=name, category=cat, price=price, image=img, desc=desc)
            products_list.append(p)
        
        db.session.bulk_save_objects(products_list)
        db.session.commit()
        print(">>> 100 Products Created!")

        # تأكد إن المكان ده موجود في ملف app.py
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# --- ضيف السطرين دول عشان لو الفولدر مش موجود يعمله هو أوتوماتيك ---
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


    def __repr__(self):
        return f'<Ingredient {self.name}>'


# --- Admin: Add Ingredient ---
@app.route('/admin/add_ingredient', methods=['POST'])
@login_required
def add_ingredient():
    if not current_user.is_admin:
        return redirect(url_for('home'))
        
    name = request.form['name']
    category = request.form['category']
    price = float(request.form['price'])
    color = request.form['color']
    
    new_ing = Ingredient(name=name, category=category, price=price, color=color)
    db.session.add(new_ing)
    db.session.commit()
    
    flash('Ingredient added successfully!', 'success')
    return redirect(url_for('lab'))

# --- مسار تحديث أسعار الزجاجات ---
@app.route('/admin/update_prices', methods=['POST'])
@login_required
def update_prices():
    # حماية: للأدمن فقط
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    # تحديث الأسعار بالقيم الجديدة من الفورم
    app.config['BOTTLE_PRICES']['50'] = float(request.form['price_50'])
    app.config['BOTTLE_PRICES']['100'] = float(request.form['price_100'])
    app.config['BOTTLE_PRICES']['200'] = float(request.form['price_200'])
    
    flash('Bottle prices updated successfully!', 'success')
    return redirect(url_for('lab'))
# --- Admin: Delete Ingredient ---
@app.route('/admin/delete_ingredient/<int:id>')
@login_required
def delete_ingredient(id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
        
    ing = Ingredient.query.get_or_404(id)
    db.session.delete(ing)
    db.session.commit()
    
    flash('Ingredient deleted!', 'success')
    return redirect(url_for('lab'))

# --- AI Scent Analyzer (Gemini Backend) ---
@app.route('/analyze_scent', methods=['POST'])
def analyze_scent():
    data = request.get_json()
    recipe = data.get('recipe', {})
    stats = data.get('stats', {})

    # 1. تجهيز وصف الخلطة عشان Gemini يفهمها
    blend_desc = (
        f"Top Note: {recipe.get('top', {}).get('name')} ({stats.get('top')}%), "
        f"Heart Note: {recipe.get('heart', {}).get('name')} ({stats.get('heart')}%), "
        f"Base Note: {recipe.get('base', {}).get('name')} ({stats.get('base')}%)."
    )

    # 2. تجهيز الموديل
    model = genai.GenerativeModel('gemini-1.5-flash')

    # 3. السؤال (Prompt)
    prompt = f"""
    You are a world-class perfumer. Analyze this perfume blend: "{blend_desc}".
    
    Write a short, sophisticated description (max 40 words).
    Then, suggest the best Occasion and Time to wear it.
    
    Format your response EXACTLY like this using HTML tags:
    [Description text here]<br><br>
    📅 <strong>Occasion:</strong> [Occasion here]<br>
    ⏰ <strong>Time:</strong> [Time/Season here]
    
    Do not add any intro or markdown, just the HTML string.
    """

    try:
        # 4. إرسال الطلب لجوجل
        response = model.generate_content(prompt)
        ai_reply = response.text
        return jsonify({'result': ai_reply})

    except Exception as e:
        print(f"Gemini Error: {e}")
        fallback = "The AI nose is currently congested. Please try again later! 🤧"
        return jsonify({'result': fallback})
    
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True)