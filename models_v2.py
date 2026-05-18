# 导入SQLAlchemy核心模块，用于数据库连接和字段定义
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, func, event
# 导入SQLAlchemy的ORM关系映射工具（兼容旧版SQLAlchemy 1.3的导入方式）
from sqlalchemy.orm import relationship, sessionmaker
# 导入声明式基类（旧版SQLAlchemy 1.3需要从ext.declarative导入）
from sqlalchemy.ext.declarative import declarative_base
# 导入Python的日期时间模块，用于设置具体的完成时间
from datetime import datetime

# 创建SQLite数据库引擎，指定新的数据库文件路径，echo=False表示不输出SQL日志
engine = create_engine('sqlite:///magnesium_order_system_v2.db', echo=False)

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


# 定义订单表模型，存储订单主信息（产品明细拆分到order_items表）
class Order(Base):
    # 指定该模型对应的数据库表名为orders
    __tablename__ = 'orders'
    
    # 订单唯一标识，整数类型，设置为主键并自动递增
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 关联的客户ID，整数类型，外键关联到customers表的id字段
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    # 订单总金额，浮点数类型，默认0.0，由程序自动汇总所有明细小计得出
    total_amount = Column(Float, nullable=False, default=0.0)
    # 订单当前状态，字符串类型，支持：待审核/待设计/待生产/生产中/已完成/已取消
    status = Column(String(20), nullable=False, default='待审核')
    # 订单创建时间，日期时间类型，默认值为插入数据时的当前系统时间
    created_at = Column(DateTime, default=func.now())
    
    # 建立与客户表的双向关联，通过order.customer可以访问该订单所属的客户对象
    customer = relationship("Customer", back_populates="orders")
    # 建立与订单明细表的一对多关系，一个订单可以包含多个产品明细
    # cascade='all, delete-orphan'表示删除订单时自动删除关联的所有明细
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    # 建立与拼版表的一对一关系，一个订单对应唯一一条拼版记录
    # uselist=False表示返回单对象而非列表，形成一对一关系
    plate_layout = relationship("PlateLayout", back_populates="order", uselist=False, cascade="all, delete-orphan")
    # 建立与生产日志表的一对多关系，一个订单可有多条生产进度记录
    logs = relationship("ProductionLog", back_populates="order", cascade="all, delete-orphan")


# 定义订单明细表模型，存储订单中每个产品的具体信息
class OrderItem(Base):
    # 指定该模型对应的数据库表名为order_items
    __tablename__ = 'order_items'
    
    # 明细唯一标识，整数类型，设置为主键并自动递增
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 关联的订单ID，整数类型，外键关联到orders表的id字段
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    # 产品类型，字符串类型，最大长度20个字符
    product_type = Column(String(20), nullable=False)
    # 产品长度，浮点数类型，单位毫米(mm)，不允许为空
    length_mm = Column(Float, nullable=False)
    # 产品宽度，浮点数类型，单位毫米(mm)，不允许为空
    width_mm = Column(Float, nullable=False)
    # 产品厚度，浮点数类型，单位毫米(mm)，不允许为空
    thickness_mm = Column(Float, nullable=False)
    # 产品数量，整数类型，不允许为空
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


# 定义拼版表模型，存储订单的拼版设计信息（与订单一对一关系）
class PlateLayout(Base):
    # 指定该模型对应的数据库表名为plate_layouts
    __tablename__ = 'plate_layouts'
    
    # 拼版记录唯一标识，整数类型，设置为主键并自动递增
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 关联的订单ID，整数类型，外键关联到orders表的id字段，一对一关系
    # unique=True约束确保一个订单只能有一条拼版记录
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False, unique=True)
    # 拼版设计文件在服务器上的存储路径，字符串类型，最大长度255个字符
    layout_file_path = Column(String(255))
    # 材料利用率，浮点数类型，单位为百分比，如85.5表示85.5%
    material_usage_rate = Column(Float)
    # 拼版后的整体尺寸描述，字符串类型，如"600×1000mm"
    layout_size = Column(String(50))
    # 设计师填写的备注信息，字符串类型，最大长度500个字符
    designer_note = Column(String(500))
    # 拼版记录的创建时间，日期时间类型，默认值为当前系统时间
    created_at = Column(DateTime, default=func.now())
    
    # 建立与订单表的双向一对一关联，通过plate_layout.order可以访问所属订单
    order = relationship("Order", back_populates="plate_layout")


# 定义生产日志表模型，记录订单在生产各环节的执行情况（与订单一对多关系）
class ProductionLog(Base):
    # 指定该模型对应的数据库表名为production_logs
    __tablename__ = 'production_logs'
    
    # 日志记录唯一标识，整数类型，设置为主键并自动递增
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 关联的订单ID，整数类型，外键关联到orders表的id字段
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    # 生产环节名称，字符串类型，如晒版/蚀刻/质检/包装
    stage = Column(String(20), nullable=False)
    # 该环节的操作人员姓名，字符串类型，最大长度50个字符
    operator = Column(String(50))
    # 当前环节的执行状态，字符串类型，进行中或已完成
    status = Column(String(20), nullable=False, default='进行中')
    # 该环节的完成时间，日期时间类型，允许为空（未完成时为空）
    completed_at = Column(DateTime)
    # 质检环节拍照对比图的文件路径，字符串类型，最大长度255个字符
    photo_path = Column(String(255))
    
    # 建立与订单表的双向关联，通过log.order可以访问所属的主订单对象
    order = relationship("Order", back_populates="logs")


# 定义SQLAlchemy事件监听函数，在插入OrderItem数据之前自动触发
# 用于自动计算该明细的面积(area)和小计金额(subtotal)，确保INSERT时携带正确数值
@event.listens_for(OrderItem, 'before_insert')
# 定义接收mapper映射器、数据库连接和目标对象的参数
def auto_calculate_item_insert(mapper, connection, target):
    # 计算单件产品的面积：长(mm)×宽(mm)÷100 = 单件面积(cm2)，因为1cm2=100mm2
    single_area = (target.length_mm * target.width_mm) / 100.0
    # 计算该明细的总面积：单件面积 × 订购数量，单位平方厘米
    target.area = single_area * target.quantity
    # 计算该明细的小计金额：总面积 × 每平方厘米单价
    target.subtotal = target.area * target.unit_price


# 定义SQLAlchemy事件监听函数，在更新OrderItem数据之前自动触发
# 用于在明细信息修改时重新自动计算面积和小计金额，确保UPDATE时携带正确数值
@event.listens_for(OrderItem, 'before_update')
# 定义接收mapper映射器、数据库连接和待更新对象的参数
def auto_calculate_item_update(mapper, connection, target):
    # 重新计算单件产品的面积（毫米转厘米）：长(mm)×宽(mm)÷100
    single_area = (target.length_mm * target.width_mm) / 100.0
    # 重新计算该明细的总面积：单件面积 × 数量
    target.area = single_area * target.quantity
    # 重新计算该明细的小计金额：总面积 × 单价
    target.subtotal = target.area * target.unit_price


# 定义SQLAlchemy事件监听函数，在插入OrderItem数据之后自动触发
# 通过原生SQL直接更新订单总金额，避免ORM inner-flush冲突和递归问题
@event.listens_for(OrderItem, 'after_insert')
# 定义接收mapper映射器、数据库连接和目标对象的参数
def update_order_total_after_insert(mapper, connection, target):
    # 使用原生SQL查询该订单下所有明细的subtotal之和（COALESCE确保无记录时返回0.0）
    total_result = connection.execute(
        "SELECT COALESCE(SUM(subtotal), 0.0) FROM order_items WHERE order_id = ?",
        (target.order_id,)
    ).scalar()
    # 使用原生SQL直接更新orders表中对应订单的total_amount字段
    connection.execute(
        "UPDATE orders SET total_amount = ? WHERE id = ?",
        (total_result, target.order_id)
    )


# 定义SQLAlchemy事件监听函数，在更新OrderItem数据之后自动触发
# 通过原生SQL重新汇总并同步更新订单总金额
@event.listens_for(OrderItem, 'after_update')
# 定义接收mapper映射器、数据库连接和待更新对象的参数
def update_order_total_after_update(mapper, connection, target):
    # 使用原生SQL查询该订单下所有明细的subtotal之和
    total_result = connection.execute(
        "SELECT COALESCE(SUM(subtotal), 0.0) FROM order_items WHERE order_id = ?",
        (target.order_id,)
    ).scalar()
    # 使用原生SQL直接更新orders表中对应订单的total_amount字段
    connection.execute(
        "UPDATE orders SET total_amount = ? WHERE id = ?",
        (total_result, target.order_id)
    )


# 定义SQLAlchemy事件监听函数，在删除OrderItem数据之后自动触发
# 通过原生SQL重新汇总并更新订单总金额
@event.listens_for(OrderItem, 'after_delete')
# 定义接收mapper映射器、数据库连接和待删除对象的参数
def update_order_total_after_delete(mapper, connection, target):
    # 使用原生SQL查询该订单下剩余所有明细的subtotal之和
    total_result = connection.execute(
        "SELECT COALESCE(SUM(subtotal), 0.0) FROM order_items WHERE order_id = ?",
        (target.order_id,)
    ).scalar()
    # 使用原生SQL直接更新orders表中对应订单的total_amount字段
    connection.execute(
        "UPDATE orders SET total_amount = ? WHERE id = ?",
        (total_result, target.order_id)
    )


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
            # 初始化订单总金额为0.0，后续会自动根据明细计算更新
            total_amount=0.0,
            # 设置订单初始状态为'待审核'
            status='待审核'
        )
        # 将新订单对象添加到当前会话的待提交队列中
        session.add(order)
        # 提交订单数据，让数据库生成订单ID，供后续明细和拼版关联
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
        # 提交所有订单明细，触发before_insert事件自动计算面积、小计
        # 同时触发before_flush事件自动汇总订单总金额
        session.commit()
        
        # 创建该订单的拼版记录（一对一关系）
        plate = PlateLayout(
            # 关联到上面创建的订单ID
            order_id=order.id,
            # 设置拼版设计文件的路径
            layout_file_path='/layouts/order_01_layout.pdf',
            # 设置材料利用率为87.5%
            material_usage_rate=87.5,
            # 设置拼版后的整体尺寸描述
            layout_size='600×1000mm',
            # 设置设计师的备注说明
            designer_note='烫金版与雕刻版拼在一版，注意套准精度'
        )
        # 将拼版记录添加到会话
        session.add(plate)
        # 提交拼版记录到数据库
        session.commit()
        
        # 创建第一条生产日志：晒版环节（已完成）
        log1 = ProductionLog(
            # 关联到该订单ID
            order_id=order.id,
            # 设置生产环节为晒版
            stage='晒版',
            # 设置操作人为王师傅
            operator='王师傅',
            # 设置状态为已完成
            status='已完成',
            # 设置完成时间为当前Python系统时间
            completed_at=datetime.now()
        )
        
        # 创建第二条生产日志：蚀刻环节（进行中）
        log2 = ProductionLog(
            # 关联到同一个订单ID
            order_id=order.id,
            # 设置生产环节为蚀刻
            stage='蚀刻',
            # 设置操作人为李师傅
            operator='李师傅',
            # 设置状态为进行中
            status='进行中',
            # 未完成，completed_at保持为空None
            completed_at=None
        )
        
        # 将第一条生产日志添加到会话
        session.add(log1)
        # 将第二条生产日志添加到会话
        session.add(log2)
        # 提交生产日志到数据库
        session.commit()
        
        # 打印测试数据插入成功的提示信息
        print("测试数据已插入成功！")
        # 返回订单ID，供后续的查询演示函数使用
        return order.id
    finally:
        # 无论操作成功与否，最后都要关闭数据库会话，释放数据库连接资源
        session.close()


# 定义查询并打印订单完整信息的演示函数
def query_order_full_info(order_id):
    # 创建一个新的数据库会话实例
    session = Session()
    try:
        # 根据订单ID查询订单主表信息，并同时关联查询客户信息
        order = session.query(Order).filter_by(id=order_id).first()
        # 如果未找到对应订单，打印提示信息并直接返回
        if not order:
            print(f"未找到ID为 {order_id} 的订单")
            return
        
        # 打印订单完整信息的大标题
        print(f"\n==================== 订单完整信息 ====================")
        # 打印该订单的所属客户公司名称
        print(f"【客户】{order.customer.company_name}")
        # 打印该订单的联系人及电话
        print(f"【联系人】{order.customer.contact_person} | {order.customer.phone}")
        # 打印该订单的当前状态
        print(f"【订单状态】{order.status}")
        # 打印该订单的总金额（已自动汇总所有明细小计）
        print(f"【订单总金额】{order.total_amount} 元")
        # 打印该订单的创建时间
        print(f"【创建时间】{order.created_at}")
        print("-" * 60)
        
        # 打印产品明细列表的小标题
        print("【产品明细】")
        # 通过订单的relationship关系获取该订单下的所有明细对象列表
        items = order.items
        # 遍历订单下的每一条明细，并打印详细信息
        for idx, item in enumerate(items, start=1):
            # 打印当前明细的序号和产品类型
            print(f"  {idx}. {item.product_type}")
            # 打印该明细的尺寸（长×宽）和厚度
            print(f"     尺寸：{item.length_mm}mm × {item.width_mm}mm × {item.thickness_mm}mm")
            # 打印该明细的数量
            print(f"     数量：{item.quantity} 个")
            # 打印该明细的单价（元/平方厘米）
            print(f"     单价：{item.unit_price} 元/cm2")
            # 打印该明细的总面积（平方厘米）
            print(f"     面积：{item.area} cm2")
            # 打印该明细的小计金额
            print(f"     小计：{item.subtotal} 元")
            # 打印该明细的设计稿文件路径
            print(f"     设计稿：{item.file_path}")
        
        print("-" * 60)
        
        # 打印拼版信息的小标题
        print("【拼版信息】")
        # 通过订单的relationship一对一关系获取拼版对象
        plate = order.plate_layout
        # 判断该订单是否有拼版记录
        if plate:
            # 打印拼版文件路径
            print(f"  拼版文件：{plate.layout_file_path}")
            # 打印拼版尺寸
            print(f"  拼版尺寸：{plate.layout_size}")
            # 打印材料利用率
            print(f"  材料利用率：{plate.material_usage_rate}%")
            # 打印设计师备注
            print(f"  设计师备注：{plate.designer_note}")
            # 打印拼版创建时间
            print(f"  创建时间：{plate.created_at}")
        else:
            # 如果没有拼版记录，打印提示信息
            print("  暂无拼版信息")
        
        print("-" * 60)
        
        # 打印生产进度的小标题
        print("【生产进度】")
        # 通过订单的relationship一对多关系获取所有生产日志列表
        logs = order.logs
        # 判断该订单是否有生产日志记录
        if logs:
            # 遍历所有生产日志并打印
            for idx, log in enumerate(logs, start=1):
                # 打印当前日志的序号、环节和操作人
                print(f"  {idx}. 【{log.stage}】 操作人：{log.operator}")
                # 打印该环节的状态
                print(f"     状态：{log.status}")
                # 判断该环节是否已完成，打印完成时间或提示未完成
                if log.completed_at:
                    print(f"     完成时间：{log.completed_at}")
                else:
                    print(f"     完成时间：--")
                # 如果有质检拍照路径，则打印出来
                if log.photo_path:
                    print(f"     拍照路径：{log.photo_path}")
        else:
            # 如果没有生产日志，打印提示信息
            print("  暂无生产记录")
        
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
    # 调用订单完整信息查询函数，展示该订单的所有关联信息
    query_order_full_info(order_id)


# 判断当前脚本是否作为主程序直接运行（而非被其他模块导入）
if __name__ == '__main__':
    # 如果是直接运行，则调用主函数开始执行
    main()
