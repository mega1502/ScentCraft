document.addEventListener("DOMContentLoaded", function() {

    // --- 1. كود موحد لكل الصفحات ---
    const siteHeader = document.getElementById("site-header");
    const menuButton = document.getElementById("mobile-menu-btn");

    // الكود هيشتغل لو لقى الهيدر والزرار
    if (siteHeader && menuButton) {
        
        // --- أ) تأثير الـ Scroll (لكل الصفحات) ---
        function handleScroll() {
            if (window.scrollY > 50) {
                siteHeader.classList.add("scrolled");
            } else {
                siteHeader.classList.remove("scrolled");
            }
        }
        // تطبيق تأثير السكرول على كل الصفحات
        window.addEventListener("scroll", handleScroll);
        // استدعاء الدالة أول مرة عشان لو الصفحة فتحت وهي أصلاً عاملة سكرول
        handleScroll(); 


        // --- ب) فتح وإغلاق قائمة الموبايل (لكل الصفحات) ---
        const mainNav = document.getElementById("main-nav");
        const headerActions = document.querySelector(".header-actions");
        const headerContainer = siteHeader.querySelector(".container"); 

        function toggleMenu() {
            mainNav.classList.toggle("active");
            headerActions.classList.toggle("active"); 
            
            if (mainNav.classList.contains("active")) {
                // لو القائمة فتحت، انقل الأزرار جواها
                mainNav.appendChild(headerActions);
            } else {
                // لو القائمة قفلت، رجع الأزرار مكانها (قبل زرار الموبايل)
                headerContainer.insertBefore(headerActions, menuButton);
            }
        }
        menuButton.addEventListener("click", toggleMenu);
    } // نهاية الكود الموحد

    // --- (تم حذف كود المتجر المنفصل) ---

});
// دالة إتمام الطلب
function checkout() {
    const cart = JSON.parse(localStorage.getItem('cart')) || [];
    
    if (cart.length === 0) {
        alert("Your cart is empty!");
        return;
    }

    // زرار التحميل عشان العميل يعرف إننا بنعالج الطلب
    const checkoutBtn = document.querySelector('.checkout-btn');
    const originalText = checkoutBtn.innerText;
    checkoutBtn.innerText = "Processing...";
    checkoutBtn.disabled = true;

    fetch('/checkout', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ items: cart }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // 1. فضي السلة
            localStorage.removeItem('cart');
            updateCartDisplay();
            toggleCart(); // اقفل السلة الجانبية
            
            // 2. طلع رسالة نجاح
            alert("Order placed successfully! We will contact you soon.");
            
            // 3. حوله لصفحة البروفايل عشان يشوف الاوردر
            window.location.href = "/profile";
        } else {
            alert("Something went wrong: " + data.message);
            checkoutBtn.innerText = originalText;
            checkoutBtn.disabled = false;
        }
    })
    .catch((error) => {
        console.error('Error:', error);
        alert("Please log in first to place an order.");
        window.location.href = "/login"; // لو مش مسجل دخول، وديه يسجل
    });
}

// اربط الزرار بالدالة دي
document.querySelector('.checkout-btn').addEventListener('click', checkout);
