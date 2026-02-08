
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
from flask import Flask, render_template, request, jsonify
import time #
# هنا بتحط مفتاحك اللي هتجيبه من Google AI Studio
# يفضل تحطه في متغيرات البيئة، بس للتجربة ممكن تحطه هنا
from jinja2 import ChoiceLoader, FileSystemLoader

app = Flask(__name__)

app.config['SECRET_KEY'] = 'mysecretkey123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scentcraft.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
# ضيف السطر ده تحت إعدادات app.config
app.config['BOTTLE_PRICES'] = {'50': 50, '100': 80, '200': 120}
# ⚠️ مهم جداً: حط مفتاح الـ API بتاعك هنا
# ممكن تجيبه مجاناً من: https://aistudio.google.com/app/apikey
# إعداد مفتاح جوجل جيمناي
os.environ["GEMINI_API_KEY"] = "AIzaSyAO2-H3cHlDDMuMttfMXhtGlLKTs3znE54"
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

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
    image = db.Column(db.String(500), default='https://via.placeholder.com/300')
    desc = db.Column(db.Text)
    # شيلنا السطر بتاع stock خلاص

# --- 2. جدول أكواد الخصم (Promo Codes) ---
class PromoCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False) # الكود زي "WEZZA20"
    discount = db.Column(db.Integer, nullable=False) # نسبة الخصم (مثلاً 20)
    is_active = db.Column(db.Boolean, default=True)

# --- 3. جدول وصفات المستخدم (Saved Formulas) ---
class SavedFormula(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(500), nullable=False) # الوصفة (Top: Lemon...)
    price = db.Column(db.Float, nullable=False) # حفظنا السعر عشان العرض
    date = db.Column(db.DateTime, default=datetime.now)

# *ملحوظة:* بعد ما تضيف دول، لازم تعمل recreate للداتا بيز أو تضيف العواميد يدوياً لو الداتا بيز فيها بيانات مهمة.
# لو لسه في الأول، امسح ملف instance/site.db وشغل التطبيق من جديد.
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

# --- 1. تعديل الراوت بتاع البروفايل (التحويلة الذكية) ---
# --- 2. تحديث دالة البروفايل (Profile Route) ---
@app.route('/profile')
@login_required
def profile():
    # +++ التعديل الذكي +++
    # لو المستخدم أدمن، وديه فوراً على لوحة القيادة
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # لو مستخدم عادي، اعرض له البروفايل وطلباته
    my_formulas = SavedFormula.query.filter_by(user_id=current_user.id).order_by(SavedFormula.date.desc()).all()
    my_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.date.desc()).all()
    
    return render_template('profile.html', user=current_user, orders=my_orders, formulas=my_formulas)

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

# --- 1. حفظ التركيبة (Save Recipe) ---
# --- 3. تحديث دالة الحفظ (Save Formula Route) ---
@app.route('/save_formula', methods=['POST'])
@login_required
def save_formula():
    data = request.get_json()
    formula_name = data.get('name')
    formula_details = data.get('details')
    formula_price = data.get('price') # استقبلنا السعر
    
    if not formula_name or not formula_details:
        return jsonify({'status': 'error', 'message': 'Missing data'})
    
    # حفظ في الداتا بيز
    new_formula = SavedFormula(
        user_id=current_user.id, 
        name=formula_name, 
        details=formula_details,
        price=formula_price
    )
    db.session.add(new_formula)
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': 'Recipe Saved to Profile!'})
# --- 4. إضافة دالة لحذف الوصفة (اختياري بس مهم) ---
@app.route('/delete_formula/<int:id>')
@login_required
def delete_formula(id):
    formula = SavedFormula.query.get_or_404(id)
    if formula.user_id == current_user.id:
        db.session.delete(formula)
        db.session.commit()
    return redirect(url_for('profile'))

# --- 2. اختبار الشخصية (AI Matchmaker) ---
@app.route('/matchmaker', methods=['GET', 'POST'])
def matchmaker():
    if request.method == 'POST':
        # لوجيك بسيط للاقتراح
        answers = request.form
        # مثال: لو اختار "صباحي" و "منعش" -> رشحله حمضيات
        if answers.get('vibe') == 'fresh' or answers.get('time') == 'morning':
            recommendation = "Citrus Explosion (Lab Recipe: 50% Lemon, 30% Bergamot, 20% Musk)"
        elif answers.get('vibe') == 'romantic':
            recommendation = "Dior Sauvage (Shop)"
        else:
            recommendation = "Royal Oud Mix (Lab Recipe: 60% Oud, 40% Rose)"
            
        return render_template('matchmaker_result.html', result=recommendation)
    return render_template('matchmaker.html')

# --- 3. التحقق من كود الخصم ---
@app.route('/check_promo', methods=['POST'])
def check_promo():
    data = request.get_json()
    code_input = data.get('code')
    promo = PromoCode.query.filter_by(code=code_input, is_active=True).first()
    
    if promo:
        return jsonify({'valid': True, 'discount': promo.discount})
    return jsonify({'valid': False})

# --- 4. تحديث الدفع (Checkout) ليشمل المخزون والخصم ---
@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    try:
        data = request.get_json()
        cart_items = data.get('items', [])
        
        if not cart_items:
            return jsonify({'status': 'error', 'message': 'Cart is empty'})
        
        # 1. حساب السعر الإجمالي مباشرة (بدون مراجعة مخزون)
        total_price = sum(item['price'] * item.get('quantity', 1) for item in cart_items)

        # 2. إنشاء الأوردر الأساسي
        new_order = Order(
            user_id=current_user.id,
            total=total_price,
            status='Processing',
            date=datetime.now()
        )
        db.session.add(new_order)
        db.session.commit()
        
        # 3. حفظ المنتجات وتحديد نوعها (عشان الداشبورد تفضل شغالة)
        for item in cart_items:
            # بنجيب التفاصيل
            raw_details = item.get('details', '')
            
            # لو التفاصيل فاضية أو شرطة، نكتب "Standard Collection" عشان تتحسب مبيعات متجر
            if not raw_details or raw_details.strip() in ['-', '']:
                final_details = 'Standard Collection'
            else:
                # غير كده تبقى وصفة معمل
                final_details = raw_details

            order_item = OrderItem(
                order_id=new_order.id,
                product_name=item['name'],
                product_price=item['price'],
                quantity=item.get('quantity', 1),
                details=final_details
            )
            db.session.add(order_item)
        
        db.session.commit()
        return jsonify({'status': 'success'})

    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Checkout Failed'}), 500

    except Exception as e:
        print(f"Error in checkout: {e}") # ده هيطبعلك سبب المشكلة في التيرمينال عشان نشوفه
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'System Error. Check Console.'}), 500

@app.route('/order_action/<int:order_id>/<action>')
@login_required
def order_action(order_id, action):
    order = Order.query.get_or_404(order_id)
    
    # حماية: لازم الأوردر يكون بتاع المستخدم الحالي
    if order.user_id != current_user.id:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('profile'))
    
    # --- التعديل هنا: المسح النهائي ---
    if action == 'cancel' and order.status == 'Processing':
        # 1. مسح تفاصيل المنتجات الأول (عشان مرتبطة بالأوردر)
        for item in order.items:
            db.session.delete(item)
        
        # 2. مسح الأوردر نفسه
        db.session.delete(order)
        db.session.commit()
        
        flash('Order removed from history successfully.', 'info')
        # كأن الأوردر لم يكن
        
    elif action == 'confirm' and order.status == 'Shipped':
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
# --- Seed Data (تجهيز البيانات + حساب الأدمن + المنتجات الحقيقية) ---
# --- Seed Data (تجهيز البيانات + حساب الأدمن + صور المنتجات الحقيقية) ---
# --- Seed Data (تجهيز البيانات + حساب الأدمن + 50 منتج حقيقي) ---
def seed_data():
    # 1. إنشاء حساب الأدمن الثابت
    admin_email = "admin@scentcraft.com"
    if not User.query.filter_by(email=admin_email).first():
        admin_user = User(
            name="ScentCraft Manager",
            email=admin_email,
            password=generate_password_hash("123456", method='pbkdf2:sha256'),
            phone="01000000000",
            address="Headquarters",
            is_admin=True
        )
        db.session.add(admin_user)
        db.session.commit()
        print(">>> Admin Account Created Successfully!")

    # 2. إنشاء المنتجات الحقيقية (Real Bottle Images)
   
    
    # لو فيه منتجات أصلاً، متعملش حاجة
    if Product.query.first():
        return

    products = [
        {
            'name': 'Dior Sauvage Elixir',
            'category': 'Men',
            'price': 7800,
            'image': 'https://fimgs.net/mdimg/perfume/375x500.68415.jpg',
            'desc': 'Spicy & Woody'
        },
        {
            'name': 'Chanel No. 5',
            'category': 'Women',
            'price': 6500,
            'image': 'https://fimgs.net/mdimg/perfume/375x500.608.jpg',
            'desc': 'Floral Aldehyde'
        },
        {
            'name': 'Versace Eros',
            'category': 'Men',
            'price': 4200,
            'image': 'https://fimgs.net/mdimg/perfume/375x500.16657.jpg',
            'desc': 'Fresh, woody and slightly oriental fragrance.'
        },
        {
            'name': 'Black Opium',
            'category': 'Women',
            'price': 5400,
            'image': 'https://fimgs.net/mdimg/perfume/375x500.25324.jpg',
            'desc': 'Coffee and vanilla based sweet fragrance.'
        }
    ]

    for item in products:
        p = Product(
            name=item['name'],
            category=item['category'],
            price=item['price'],
            image=item['image'],
            desc=item['desc']
            # لاحظ: مفيش stock هنا خلاص
        )
        db.session.add(p)
    
    db.session.commit()
    print(">>> Database seeded successfully (No Stock)!")
        # ... (بعد كود المنتجات real_products) ...

    # 3. إنشاء مكونات المعمل (Virtual Lab Ingredients)
    if Ingredient.query.count() == 0:
        lab_ingredients = [
            # --- TOP NOTES (مقدمة العطر - حمضيات ومنعشات) ---
            { "name": "Bergamot ", "category": "top", "price": 15, "color": "#C8E177" }, # أخضر فاتح
            { "name": "Lemon ", "category": "top", "price": 10, "color": "#FFF44F" }, # أصفر
            { "name": "Grapefruit ", "category": "top", "price": 12, "color": "#FD5956" }, # برتقالي محمر
            { "name": "Mint ", "category": "top", "price": 9, "color": "#98FF98" }, # نعناعي
            { "name": "Lavender ", "category": "top", "price": 14, "color": "#E6E6FA" }, # بنفسجي فاتح
            { "name": "Black Pepper ", "category": "top", "price": 13, "color": "#333333" }, # رمادي غامق

            # --- HEART NOTES (قلب العطر - زهور وتوابل) ---
            { "name": "Damask Rose ", "category": "heart", "price": 20, "color": "#FF007F" }, # وردي غامق
            { "name": "Jasmine Sambac ", "category": "heart", "price": 22, "color": "#FFFFFF" }, # أبيض
            { "name": "Cinnamon ", "category": "heart", "price": 13, "color": "#D2691E" }, # بني محمر
            { "name": "Neroli ", "category": "heart", "price": 19, "color": "#FFA700" }, # برتقالي
            { "name": "Ylang-Ylang ", "category": "heart", "price": 18, "color": "#FCE883" }, # أصفر كريمي
            { "name": "Iris ", "category": "heart", "price": 28, "color": "#5D3F6A" }, # بنفسجي غامق

            # --- BASE NOTES (قاعدة العطر - أخشاب وعنبر) ---
            { "name": "Royal Oud ", "category": "base", "price": 15, "color": "#4B3621" }, # بني غامق جداً
            { "name": "White Musk ", "category": "base", "price": 20, "color": "#F5F5F5" }, # أبيض لؤلؤي
            { "name": "Madagascar Vanilla ", "category": "base", "price": 12, "color": "#F3E5AB" }, # بيج
            { "name": "Ambergris ", "category": "base", "price": 17, "color": "#FFBF00" }, # ذهبي
            { "name": "Sandalwood ", "category": "base", "price": 44, "color": "#A45A52" }, # خشب محمر
            { "name": "Patchouli ", "category": "base", "price": 13, "color": "#592720" }, # بني ترابي
            { "name": "Leather ", "category": "base", "price": 11, "color": "#8B4513" }, # بني جلد
            { "name": "Tobacco ", "category": "base", "price": 18, "color": "#6F4E37" }  # بني قهوة
        ]

        # حفظ المكونات في الداتا بيز
        for item in lab_ingredients:
            ing = Ingredient(
                name=item['name'],
                category=item['category'],
                price=item['price'],
                color=item['color']
            )
            db.session.add(ing)
        
        db.session.commit()
        print(f">>> {len(lab_ingredients)} Lab Ingredients Created Successfully!")

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
    try:
        data = request.json
        recipe = data.get('recipe')
        stats = data.get('stats')

        prompt = f"""
        Act as a professional perfumer. Analyze this custom perfume blend:
        - Top Note: {recipe['top']['name']} ({stats['top']}%)
        - Heart Note: {recipe['heart']['name']} ({stats['heart']}%)
        - Base Note: {recipe['base']['name']} ({stats['base']}%)
        
        Provide a short analysis (max 50 words) covering scent character, best occasion, and season.
        Luxury tone. No markdown symbols.
        """

        # استخدمنا الموديل ده لأنه مستقر أكتر
        model = genai.GenerativeModel('gemini-flash-latest')
        
        try:
            response = model.generate_content(prompt)
        except Exception as e:
            # لو حصل خطأ ضغط (429)، نستنى 2 ثانية ونجرب تاني
            if "429" in str(e):
                time.sleep(2)
                response = model.generate_content(prompt)
            else:
                raise e # لو خطأ تاني اظهره
        
        analysis_text = response.text.replace('*', '').strip()
        return jsonify({'result': analysis_text, 'status': 'success'})

    except Exception as e:
        print(f"AI Error: {e}")
        # رسالة لطيفة للعميل لو السيرفر مشغول جداً
        error_msg = "The Scent Expert is busy. Please try again in 10 seconds." if "429" in str(e) else f"⚠️ Error: {str(e)}"
        return jsonify({'result': error_msg, 'status': 'error'})
    # --- منطقة إدارة الاوردرات (Admin Orders) ---

# 1. صفحة عرض كل الاوردرات
@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    # هات كل الاوردرات مرتبة من الأحدث للأقدم
    orders = Order.query.order_by(Order.date.desc()).all()
    return render_template('admin_orders.html', orders=orders)

# 2. تغيير حالة الاوردر (قبول - شحن - تسليم)
@app.route('/admin/update_order/<int:order_id>/<status>')
@login_required
def update_order_status(order_id, status):
    if not current_user.is_admin:
        return redirect(url_for('home'))
        
    order = Order.query.get_or_404(order_id)
    order.status = status
    db.session.commit()
    
    flash(f'Order #{order.id} status updated to {status}', 'success')
    return redirect(url_for('admin_orders'))
# --- Admin Dashboard (لوحة التحكم المركزية) ---

# 1. عرض كل الأوردرات (الصفحة الرئيسية للأدمن)
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    # 1. جلب كل الطلبات
    all_orders = Order.query.order_by(Order.date.desc()).all()
    
    # 2. الحسابات المالية (الإيرادات والطلبات المعلقة)
    total_revenue = sum(order.total for order in all_orders if order.status != 'Cancelled')
    pending_orders = sum(1 for order in all_orders if order.status == 'Processing')

    # 3. محرك الذكاء (Market Intelligence Engine)
    # ده الجزء اللي بيحسب مين بيبيع أكتر (المعمل ولا المتجر)
    lab_sales = 0
    shop_sales = 0
    
    for order in all_orders:
        if order.status != 'Cancelled':
            for item in order.items:
                # لو التفاصيل "Standard Collection" أو فاضية -> يبقى متجر
                # غير كده -> يبقى معمل
                details = item.details
                if not details or details.strip() in ['-', '', 'Standard Collection']:
                    shop_sales += item.quantity
                else:
                    lab_sales += item.quantity
    
    # 4. حساب النسب المئوية للشريط الملون
    total_items = lab_sales + shop_sales
    if total_items > 0:
        lab_pct = int((lab_sales / total_items) * 100)
        shop_pct = 100 - lab_pct
    else:
        lab_pct = 0
        shop_pct = 0

    return render_template('admin_dashboard.html', 
                           orders=all_orders, 
                           revenue=total_revenue, 
                           pending=pending_orders,
                           lab_sales=lab_sales,
                           shop_sales=shop_sales,
                           lab_pct=lab_pct,
                           shop_pct=shop_pct)

# 2. تغيير حالة الأوردر (أكشن للأدمن)
@app.route('/admin/order_status/<int:order_id>/<new_status>')
@login_required
def change_order_status(order_id, new_status):
    if not current_user.is_admin:
        return redirect(url_for('home'))
        
    order = Order.query.get_or_404(order_id)
    
    # --- التعديل هنا: لو الحالة Cancelled امسحه فوراً ---
    if new_status == 'Cancelled':
        # 1. مسح تفاصيل المنتجات
        for item in order.items:
            db.session.delete(item)
            
        # 2. مسح الأوردر نفسه
        db.session.delete(order)
        db.session.commit()
        flash(f"Order #{order_id} has been permanently deleted.", "info")
    
    else:
        # لو أي حالة تانية (Shipped / Delivered) نحدثها عادي
        order.status = new_status
        db.session.commit()
        flash(f"Order #{order.id} status updated to {new_status}", "success")
    
    return redirect(url_for('admin_dashboard'))
    
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True)