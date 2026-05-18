# 导入SQLAlchemy核心模块，用于数据库连接和字段定义
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, func, event
# 导入SQLAlchemy的ORM关系映射工具（兼容旧版SQLAlchemy 1.3的导入方式）
from sqlalchemy.orm import relationship, sessionmaker
# 导入声明式基类（旧版SQLAlchemy 1.3需要从ext.declarative导入）
from sqlalchemy.ext.declarative import declarative_base

# 创建SQLite数据库引擎，指定数据库文件路径，echo=False表示不输出SQL日志
engine = create_engine('sqlite:///magnesium_order_system.db', echo=False)

# 创建会话工厂类，绑定到上面创建的数据库引擎
Session = sessionmaker(bind=engine)

# 创建ORM声明式基类，所有模型类都需要继承这个基类
Base = declarative_base()


# 定义客户表模型，存储客户基本信息
class Customer(Base):
    # 指定该模型对应的数据库表名为customers
    __tablename__ = 'customers'
    
    # 客户唯一标识，整数类型，设置为主键并自动递增
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 客户公司全称，字符串类型，最大长度100个字符，不允许为空
    company_name = Column(String(100), nullable=False)
    # 联系人姓名，字符串类型，最大长度50个字符
    contact_person = Column(String(50))
    # 联系人手机号码，字符串类型，最大长度20个字符
    phone = Column(String(20))
    # 客户信用额度，浮点数类型，默认值为0.0元
    credit_limit = Column(Float, default=0.0)
    
    # 建立与客户订单的一对多关系，一个客户可以拥有多个订单
    # back_populates实现双向关联，通过customer.orders可以访问该客户的所有订单
    orders = relationship("Order", back_populates="customer")


# 定义订单表模型，存储订单主信息（不包含具体产品明细）
class Order(Base):
    # 指定该模型对应的数据库表名为orders
    __tablename__ = 'orders'
    
    # 订单唯一标识，整数类型，设置为主键并自动递增
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 关联的客户ID，整数类型，外键关联到customers表的id字段，建立表与表之间的关联
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    # 订单总金额，浮点数类型，不允许为空，存储该订单下所有明细的小计之和
    total_amount = Column(Float, nullable=False, default=0.0)
    # 订单当前状态，字符串类型，最大长度20个字符，默认状态为'待审核'
    status = Column(String(20), nullable=False, default='待审核')
    # 订单创建时间，日期时间类型，默认值为插入数据时的当前系统时间
    created_at = Column(DateTime, default=func.now())
    
    # 建立与客户表的双向关联，通过order.customer可以访问该订单所属的客户对象
    customer = relationship("Customer", back_populates="orders")
    # 建立与订单明细表的一对多关系，一个订单可以包含多个产品明细
    # cascade='all, delete-orphan'表示删除订单时自动删除关联的所有明细
    # back_populates实现双向关联，通过order.items可以访问该订单的所有明细
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


# 定义订单明细表模型，存储订单中每个产品的具体信息
class OrderItem(Base):
    # 指定该模型对应的数据库表名为order_items
    __tablename__ = 'order_items'
    
    # 明细唯一标识，整数类型，设置为主键并自动递增
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 关联的订单ID，整数类型，外键关联到orders表的id字段，指明该明细属于哪个订单
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    # 产品类型，字符串类型，最大长度20个字符，可选值包括：烫金版/压纹版/浮雕版/雕刻版
    product_type = Column(String(20), nullable=False)
    # 产品长度，浮点数类型，单位毫米(mm)，不允许为空
    length_mm = Column(Float, nullable=False)
    # 产品宽度，浮点数类型，单位毫米(mm)，不允许为空
    width_mm = Column(Float, nullable=False)
    # 产品厚度，浮点数类型，单位毫米(mm)，可选值为1.5/2.0/3.0，不允许为空
    thickness_mm = Column(Float, nullable=False)
    # 产品数量，整数类型，不允许为空，表示该产品的订购个数
    quantity = Column(Integer, nullable=False)
    # 产品单价，浮点数类型，单位为元/平方厘米，不允许为空
    unit_price = Column(Float, nullable=False)
    # 产品总面积，浮点数类型，单位平方厘米，由系统根据公式自动计算得出
    area = Column(Float, nullable=False, default=0.0)
    # 该明细的小计金额，浮点数类型，由系统根据面积×单价自动计算得出
    subtotal = Column(Float, nullable=False, default=0.0)
    # 客户上传的设计稿文件路径，字符串类型，最大长度255个字符
    file_path = Column(String(255))
    
    # 建立与订单表的双向关联，通过item.order可以访问该明细所属的主订单对象
    order = relationship("Order", back_populates="items")


# 定义SQLAlchemy事件监听函数，在插入OrderItem数据之前自动触发
# 用于自动计算面积(area)和小计金额(subtotal)
@event.listens_for(OrderItem, 'before_insert')
# 定义接收mapper映射器、数据库连接和目标对象的参数
def auto_calculate_on_insert(mapper, connection, target):
    # 计算单件产品的面积：将毫米转换为厘米后相乘，长(mm)×宽(mm)÷100 = 单件面积(cm²)
    single_area = (target.length_mm * target.width_mm) / 100.0
    # 计算该明细的总面积：单件面积 × 订购数量，单位平方厘米
    target.area = single_area * target.quantity
    # 计算该明细的小计金额：总面积 × 每平方厘米单价
    target.subtotal = target.area * target.unit_price


# 定义SQLAlchemy事件监听函数，在更新OrderItem数据之前自动触发
# 用于在明细信息修改时重新自动计算面积和小计金额
@event.listens_for(OrderItem, 'before_update')
# 定义接收mapper映射器、数据库连接和待更新对象的参数
def auto_calculate_on_update(mapper, connection, target):
    # 重新计算单件产品的面积（毫米转厘米）：长(mm)×宽(mm)÷100
    single_area = (target.length_mm * target.width_mm) / 100.0
    # 重新计算该明细的总面积：单件面积 × 数量
    target.area = single_area * target.quantity
    # 重新计算该明细的小计金额：总面积 × 单价
    target.subtotal = target.area * target.unit_price


# 定义创建数据库和所有表结构的函数
def init_db():
    # 根据所有继承Base的模型类，自动在SQLite数据库中创建对应的物理表
    Base.metadata.create_all(engine)
    # 在控制台打印数据库初始化完成的提示信息
    print("数据库及所有表已创建完成！")


# 定义插入测试数据的函数
def insert_test_data():
    # 创建一个新的数据库会话实例，用于执行后续的数据库操作
    session = Session()
    try:
        # 创建一个客户对象：上海镁印科技有限公司
        customer = Customer(
            # 设置客户公司名
            company_name='上海镁印科技有限公司',
            # 设置联系人姓名
            contact_person='张经理',
            # 设置联系电话
            phone='13800138000',
            # 设置信用额度为50000元
            credit_limit=50000.0
        )
        # 将新客户对象添加到当前会话的待提交队列中
        session.add(customer)
        # 先提交客户数据，触发数据库生成客户ID，以便后续订单关联外键
        session.commit()
        
        # 创建一个订单对象，归属上面创建的客户
        order = Order(
            # 设置该订单关联的客户ID
            customer_id=customer.id,
            # 初始化订单总金额为0，后续会根据明细自动汇总更新
            total_amount=0.0,
            # 设置订单状态为'待审核'
            status='待审核'
        )
        # 将新订单对象添加到当前会话的待提交队列中
        session.add(order)
        # 提交订单数据，让数据库生成订单ID，供后续明细关联
        session.commit()
        
        # 创建第一条订单明细：烫金版产品
        item1 = OrderItem(
            # 关联到上面创建的订单ID
            order_id=order.id,
            # 设置产品类型为烫金版
            product_type='烫金版',
            # 设置产品长度为150毫米
            length_mm=150.0,
            # 设置产品宽度为100毫米
            width_mm=100.0,
            # 设置产品厚度为1.5毫米
            thickness_mm=1.5,
            # 设置订购数量为10个
            quantity=10,
            # 设置单价为每平方厘米12元
            unit_price=12.0,
            # 设置客户上传的设计稿文件存放路径
            file_path='/uploads/artwork_01.pdf'
        )
        
        # 创建第二条订单明细：雕刻版产品
        item2 = OrderItem(
            # 关联到同一个订单ID
            order_id=order.id,
            # 设置产品类型为雕刻版
            product_type='雕刻版',
            # 设置产品长度为200毫米
            length_mm=200.0,
            # 设置产品宽度为150毫米
            width_mm=150.0,
            # 设置产品厚度为3.0毫米
            thickness_mm=3.0,
            # 设置订购数量为5个
            quantity=5,
            # 设置单价为每平方厘米35元
            unit_price=35.0,
            # 设置客户上传的设计稿文件存放路径
            file_path='/uploads/artwork_02.pdf'
        )
        
        # 将第一条明细对象添加到会话的待提交队列
        session.add(item1)
        # 将第二条明细对象添加到会话的待提交队列
        session.add(item2)
        # 提交所有订单明细，触发before_insert事件自动计算面积和小计
        session.commit()
        
        # 重新查询该订单下的所有明细，计算订单总金额
        # 通过relationship关系从订单对象获取所有关联的明细列表
        items = session.query(OrderItem).filter_by(order_id=order.id).all()
        # 使用列表生成式提取所有明细的小计金额，并用sum函数求和得到订单总金额
        total = sum(item.subtotal for item in items)
        # 将计算得到的总金额赋值给订单对象的total_amount字段
        order.total_amount = total
        # 提交更新后的订单总金额到数据库
        session.commit()
        
        # 打印测试数据插入成功的提示信息
        print("测试数据已插入成功！")
        # 返回订单ID，供后续的查询演示函数使用
        return order.id
    finally:
        # 无论操作成功与否，最后都要关闭数据库会话，释放数据库连接资源
        session.close()


# 定义查询某个订单所有明细的演示函数
def query_order_details(order_id):
    # 创建一个新的数据库会话实例
    session = Session()
    try:
        # 根据订单ID查询订单主表信息
        order = session.query(Order).filter_by(id=order_id).first()
        # 如果未找到对应订单，打印提示信息并直接返回
        if not order:
            print(f"未找到ID为 {order_id} 的订单")
            return
        
        # 打印订单基本信息的分隔标题行
        print(f"\n========== 订单ID：{order.id} 的明细列表 ==========")
        # 打印该订单所属的客户公司名称
        print(f"客户公司：{order.customer.company_name}")
        # 打印订单当前状态
        print(f"订单状态：{order.status}")
        # 打印订单创建时间
        print(f"创建时间：{order.created_at}")
        # 打印分隔线
        print("-" * 60)
        
        # 通过订单的relationship关系获取该订单下的所有明细对象列表
        items = order.items
        # 如果该订单没有任何明细记录，打印提示并返回
        if not items:
            print("该订单暂无明细记录。")
            return
        
        # 遍历订单下的每一条明细，并打印详细信息
        for idx, item in enumerate(items, start=1):
            # 打印当前明细的序号标题
            print(f"\n【明细 {idx}】")
            # 打印明细ID
            print(f"  明细ID：{item.id}")
            # 打印产品类型
            print(f"  产品类型：{item.product_type}")
            # 打印产品尺寸（长×宽）
            print(f"  尺寸：{item.length_mm}mm × {item.width_mm}mm")
            # 打印产品厚度
            print(f"  厚度：{item.thickness_mm}mm")
            # 打印订购数量
            print(f"  数量：{item.quantity} 个")
            # 打印单价（元/平方厘米）
            print(f"  单价：{item.unit_price} 元/cm2")
            # 打印自动计算的总面积（平方厘米）
            print(f"  面积：{item.area} cm2")
            # 打印自动计算的小计金额
            print(f"  小计：{item.subtotal} 元")
            # 打印设计稿文件路径
            print(f"  设计稿：{item.file_path}")
        
        # 打印分隔线
        print("-" * 60)
        # 打印该订单下所有明细的小计总和（即订单总金额）
        print(f"订单总金额：{order.total_amount} 元")
        # 打印底部分隔线
        print("=" * 60)
    finally:
        # 无论查询成功与否，最后关闭数据库会话释放资源
        session.close()


# 程序主入口函数
def main():
    # 调用数据库初始化函数，创建所有数据表
    init_db()
    # 调用测试数据插入函数，并获取生成的订单ID
    order_id = insert_test_data()
    # 调用订单明细查询函数，展示该订单的所有产品明细
    query_order_details(order_id)


# 判断当前脚本是否作为主程序直接运行（而非被其他模块导入）
if __name__ == '__main__':
    # 如果是直接运行，则调用主函数开始执行
    main()
