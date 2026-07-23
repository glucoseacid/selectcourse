"""应用入口"""
from selectcourse import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
