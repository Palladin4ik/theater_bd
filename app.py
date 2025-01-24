from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired
import psycopg2
from psycopg2 import sql

# Словарь сопоставления таблицы и её уникального идентификатора
ID_COLUMN_MAPPING = {
    "Зритель": "Код_Зрителя",
    "Спектакль": "Код_Спектакля",
    "Категория": "Код_Категории",
    "Коллектив": "Код_Коллектива",
    "Режиссер": "Код_Режиссера",
    "Место": "Код_Места",
    "Афиша": "Код_Афиши",
    "Билет": "Код_Билета",
    "Адрес": "Код_Адреса",
    "Прогоны": "Код_Прогона"
}

# Инициализация Flask и базы данных
app = Flask(__name__)
app.config.from_object('config.Config')
db = SQLAlchemy(app)

# Константы
ITEMS_PER_PAGE = 10  # Количество элементов на странице

# Форма входа
class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[InputRequired()])
    password = PasswordField('Пароль', validators=[InputRequired()])
    submit = SubmitField('Войти')

@app.context_processor
def utility_processor():
    return dict(zip=zip)

# Главная страница
@app.route('/')
def index():
    return render_template('index.html')

# Страница входа
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        if connect_to_db(username, password):
            return redirect(url_for('show_tables'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    return render_template('login.html', form=form)

# Соединение с базой данных
def connect_to_db(user, password):
    global conn, cursor
    try:
        conn = psycopg2.connect(
            dbname="theater",
            user=user,
            password=password,
            host="localhost",
            port="5432"
        )
        cursor = conn.cursor()  # Инициализация курсора
        return True
    except Exception as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return False

# Отображение таблиц
@app.route('/tables')
def show_tables():
    # Добавим таблицу "Адреса" и уберем "Афиша"
    tables = ["Зритель", "Категория", "Коллектив", "Адреса", "Режиссер", "Место", "Спектакль", "Билет", "Прогоны"]
    return render_template('index.html', tables=tables, show=True)

@app.route('/зрители_и_спектакли')
def зрители_и_спектакли():
    return redirect(url_for('view_table', table_name='зрители_и_спектакли'))

@app.route('/спектакли_и_прогоны')
def спектакли_и_прогоны():
    return redirect(url_for('view_table', table_name='спектакли_и_прогоны'))

@app.route('/места_и_занятость')
def места_и_занятость():
    return redirect(url_for('view_table', table_name='места_и_занятость'))

@app.route('/режиссеры_и_спектакли')
def режиссеры_и_спектакли():
    return redirect(url_for('view_table', table_name='режиссеры_и_спектакли'))

@app.route('/коллективы_и_адреса')
def коллективы_и_адреса():
    return redirect(url_for('view_table', table_name='коллективы_и_адреса'))

@app.route('/view_table/<table_name>', methods=['GET'])
def view_table(table_name):
    page = request.args.get('page', 1, type=int)
    filter_column = request.args.get('filter_column', '')
    filter_value = request.args.get('filter_value', '')
    sort_column = request.args.get('sort_column', '')  # Сортировка по столбцу
    sort_order = request.args.get('sort_order', 'asc')  # Порядок сортировки (asc/desc)

    ITEMS_PER_PAGE = 10  # Количество записей на страницу

    try:
        # Получение столбцов таблицы
        cursor.execute(sql.SQL("SELECT * FROM {} LIMIT 0").format(sql.Identifier(table_name)))
        columns = [desc[0] for desc in cursor.description]
    except Exception as e:
        return f"Ошибка при получении столбцов таблицы '{table_name}': {e}", 400

    if not columns:
        return f"Таблица '{table_name}' не содержит данных.", 400

    # Проверка наличия фильтрации
    where_clause = sql.SQL("")
    query_params = []
    if filter_column and filter_value:
        if filter_column not in columns:
            return f"Столбец '{filter_column}' не существует в таблице '{table_name}'.", 400
        where_clause = sql.SQL("WHERE {}::text ILIKE %s").format(sql.Identifier(filter_column))
        query_params.append(f"%{filter_value}%")

    # Логика сортировки
    order_clause = sql.SQL("")
    if sort_column in columns:
        if sort_order == 'desc':
            order_clause = sql.SQL("ORDER BY {} DESC").format(sql.Identifier(sort_column))
        else:
            order_clause = sql.SQL("ORDER BY {} ASC").format(sql.Identifier(sort_column))

    # Постраничный запрос
    query = sql.SQL("SELECT * FROM {table} {where_clause} {order_clause} LIMIT %s OFFSET %s").format(
        table=sql.Identifier(table_name),
        where_clause=where_clause,
        order_clause=order_clause
    )
    query_params.extend([ITEMS_PER_PAGE, (page - 1) * ITEMS_PER_PAGE])

    try:
        cursor.execute(query, query_params)
        rows = cursor.fetchall()
    except Exception as e:
        return f"Ошибка при выполнении запроса к таблице '{table_name}': {e}", 400

    # Подсчет общего числа строк
    count_query = sql.SQL("SELECT COUNT(*) FROM {table} {where_clause}").format(
        table=sql.Identifier(table_name),
        where_clause=where_clause
    )
    try:
        cursor.execute(count_query, query_params[:-2])  # Исключаем LIMIT и OFFSET
        total_rows = cursor.fetchone()[0]
    except Exception as e:
        return f"Ошибка при подсчете строк таблицы '{table_name}': {e}", 400

    total_pages = (total_rows // ITEMS_PER_PAGE) + (1 if total_rows % ITEMS_PER_PAGE > 0 else 0)

    can_edit=True
    # Показывать форму добавления записи для определённых таблиц
    restricted_tables = [
        'зрители_и_спектакли', 'спектакли_и_прогоны',
        'места_и_занятость', 'режиссеры_и_спектакли', 'коллективы_и_адреса'
    ]
    if (table_name not in restricted_tables):
        can_edit = True
    else:
        can_edit=False

    return render_template('view_table.html', rows=rows, columns=columns, table_name=table_name,
                           page=page, total_pages=total_pages, filter_column=filter_column,
                           filter_value=filter_value, sort_column=sort_column, sort_order=sort_order, can_edit=can_edit)

# Обработчик для добавления строки
@app.route('/add_row/<table_name>', methods=['POST'])
def add_row(table_name):
    try:
        # Получаем данные для добавления из формы
        columns = request.form.to_dict()
        column_names = columns.keys()
        values = [columns[col] for col in column_names]

        # Формируем запрос для добавления
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(map(sql.Identifier, column_names)),
            sql.SQL(', ').join([sql.Placeholder()] * len(values))
        )

        cursor.execute(query, values)
        conn.commit()  # Сохраняем изменения
        flash("Строка успешно добавлена", "success")
        return redirect(url_for('view_table', table_name=table_name))

    except Exception as e:
        conn.rollback()  # Откатываем транзакцию в случае ошибки
        print(f"Ошибка при добавлении строки: {e}")
        flash(f"Ошибка при добавлении строки: {e}", "danger")
        return redirect(url_for('view_table', table_name=table_name))


# Обработчик редактирования строки
@app.route('/edit_row/<table_name>/<row_code>', methods=['GET', 'POST'])
def edit_row(table_name, row_code):
    # Получаем название уникального идентификатора строки для данной таблицы
    row_id_column = ID_COLUMN_MAPPING.get(table_name)
    if not row_id_column:
        flash(f"Не удаётся определить идентификатор для таблицы {table_name}", 'danger')
        return redirect(url_for('view_table', table_name=table_name))
    
    # Обработка редактирования строки
    if request.method == 'POST':
        # Формирование обновлений для SQL
        updates = []
        values = []
        for column, value in request.form.items():
            if column != row_id_column:  # Исключаем идентификатор строки из редактируемых колонок
                updates.append(f'"{column}" = %s')
                values.append(value)
        
        values.append(row_code)  # Добавляем значение идентификатора строки для WHERE
        update_query = f'UPDATE "{table_name}" SET {", ".join(updates)} WHERE "{row_id_column}" = %s'
        
        try:
            cursor.execute(update_query, values)
            conn.commit()
            flash('Строка успешно отредактирована', 'success')
        except Exception as e:
            flash(f'Ошибка редактирования строки: {e}', 'danger')
        
        return redirect(url_for('view_table', table_name=table_name))

    # Загрузка данных строки для отображения в форме
    select_query = f'SELECT * FROM "{table_name}" WHERE "{row_id_column}" = %s'
    cursor.execute(select_query, (row_code,))
    row = cursor.fetchone()
    if not row:
        flash('Строка не найдена', 'danger')
        return redirect(url_for('view_table', table_name=table_name))
    
    # Получение списка столбцов таблицы
    columns = [desc[0] for desc in cursor.description]

    return render_template('edit_row.html', table_name=table_name, row=row, columns=columns, row_id_column=row_id_column)

# Обработчик для удаления строки
@app.route('/delete_row/<table_name>/<row_code>', methods=['POST'])
def delete_row(table_name, row_code):
    try:
        # Удаляем строку по уникальному идентификатору
        delete_query = sql.SQL("DELETE FROM {} WHERE {} = %s").format(
            sql.Identifier(table_name),
            sql.Identifier(ID_COLUMN_MAPPING[table_name])
        )
        cursor.execute(delete_query, (row_code,))
        conn.commit()
        flash('Запись успешно удалена', 'success')
    except Exception as e:
        print(f"Ошибка при удалении строки: {e}")
        flash('Ошибка при удалении строки', 'danger')
    
    return redirect(url_for('view_table', table_name=table_name))

# Запуск приложения
if __name__ == '__main__':
    app.run(debug=True)
