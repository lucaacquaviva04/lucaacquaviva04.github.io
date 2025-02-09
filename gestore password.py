import sys
import os
import json
import secrets
import string
import logging
from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QComboBox,
    QMessageBox, QInputDialog, QDialog, QTextBrowser, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QClipboard
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from argon2.low_level import hash_secret_raw, Type

# Configurazione del logging per registrare le attività e gli errori dell'applicazione
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='password_manager.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# ----------------------------
# Funzioni crittografiche con Argon2 per derivare le chiavi
# ----------------------------

def derive_key(master_password: str, salt: bytes) -> bytes:
    """
    Deriva una chiave di 32 byte dalla Master Password e dal salt, usando Argon2.
    I parametri (time_cost, memory_cost, parallelism) possono essere aggiustati in base alle necessità.
    """
    try:
        key = hash_secret_raw(
            secret=master_password.encode(),
            salt=salt,
            time_cost=2,
            memory_cost=65536,  # circa 64 MB di memoria
            parallelism=1,
            hash_len=32,
            type=Type.I
        )
        logger.debug("Key derived successfully.")
        return key
    except Exception as e:
        logger.exception("Error deriving key")
        raise e

def encrypt_data(plaintext: str, key: bytes) -> bytes:
    """
    Cripta il testo in chiaro usando AES-GCM.
    Ritorna il nonce concatenato al ciphertext.
    """
    try:
        aesgcm = AESGCM(key)
        nonce = os.urandom(128)  # Nonce di 96 bit
        encrypted = aesgcm.encrypt(nonce, plaintext.encode(), None)
        logger.debug("Data encrypted successfully.")
        return nonce + encrypted
    except Exception as e:
        logger.exception("Error encrypting data")
        raise e

def decrypt_data(encrypted_data: bytes, key: bytes) -> str:
    """
    Decripta i dati (nonce + ciphertext) usando AES-GCM.
    Ritorna il testo in chiaro.
    """
    try:
        aesgcm = AESGCM(key)
        nonce = encrypted_data[:128]
        ct = encrypted_data[128:]
        decrypted = aesgcm.decrypt(nonce, ct, None)
        logger.debug("Data decrypted successfully.")
        return decrypted.decode()
    except Exception as e:
        logger.exception("Error decrypting data")
        raise ValueError("Decryption failed") from e

def generate_password(length: int = 128, use_uppercase: bool = True, use_digits: bool = True, use_special: bool = True) -> str:
    """
    Genera una password casuale utilizzando il modulo secrets per una maggiore sicurezza.
    """
    characters = string.ascii_lowercase
    if use_uppercase:
        characters += string.ascii_uppercase
    if use_digits:
        characters += string.digits
    if use_special:
        characters += string.punctuation
    new_password = ''.join(secrets.choice(characters) for _ in range(length))
    logger.debug("Password generated: %s", new_password)
    return new_password

# ----------------------------
# Database persistente e criptato
# ----------------------------

class PersistentDatabase:
    """
    Gestisce le credenziali in un file JSON.
    I dati sono salvati in due partizioni:
      - Partition 1: ambiente protetto (criptato con key_main)
      - Partition 2: backup (criptato con key_backup)
    Oltre ai dati, il file contiene i sali per la derivazione delle chiavi e
    un campo di verifica ("master_verification") per confermare la correttezza della Master Password.
    """
    def __init__(self, filename: str = "db.json"):
        self.filename = filename
        self.data = {
            "main_salt": None,
            "backup_salt": None,
            "master_verification": None,
            "next_id": 1,
            "partition1": [],
            "partition2": []
        }
        self.load()

    def load(self):
        """
        Carica i dati dal file JSON se esiste, altrimenti inizializza un nuovo database.
        """
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as f:
                    self.data = json.load(f)
                logger.info("Database loaded from %s", self.filename)
            except Exception as e:
                logger.exception("Error loading database, initializing new database.")
                self.initialize_new()
        else:
            logger.info("Database file not found. Initializing new database.")
            self.initialize_new()

    def initialize_new(self):
        """
        Inizializza un nuovo database con sali casuali e struttura vuota.
        """
        self.data["main_salt"] = os.urandom(32).hex()
        self.data["backup_salt"] = os.urandom(32).hex()
        self.data["master_verification"] = None
        self.data["next_id"] = 1
        self.data["partition1"] = []
        self.data["partition2"] = []
        self.save()
        logger.info("New database initialized.")

    def save(self):
        """
        Salva i dati correnti nel file JSON.
        """
        try:
            with open(self.filename, "w") as f:
                json.dump(self.data, f)
            logger.info("Database saved to %s", self.filename)
        except Exception as e:
            logger.exception("Error saving database.")

    def add_password(self, enc_service_main: str, enc_username_main: str, enc_password_main: str,
                     enc_service_backup: str, enc_username_backup: str, enc_password_backup: str):
        """
        Aggiunge una nuova voce criptata al database.
        """
        entry = {
            "id": self.data["next_id"],
            "service": enc_service_main,
            "username": enc_username_main,
            "password": enc_password_main
        }
        backup_entry = {
            "id": self.data["next_id"],
            "service": enc_service_backup,
            "username": enc_username_backup,
            "password": enc_password_backup
        }
        self.data["partition1"].append(entry)
        self.data["partition2"].append(backup_entry)
        self.data["next_id"] += 1
        self.save()
        logger.info("New password entry added with id %d", entry["id"])

    def update_password(self, entry_id: int, enc_service_main: str, enc_username_main: str, enc_password_main: str,
                        enc_service_backup: str, enc_username_backup: str, enc_password_backup: str):
        """
        Aggiorna una voce esistente nel database.
        """
        found = False
        for entry in self.data["partition1"]:
            if entry["id"] == entry_id:
                entry["service"] = enc_service_main
                entry["username"] = enc_username_main
                entry["password"] = enc_password_main
                found = True
                break
        if not found:
            logger.error("Entry with id %d not found in partition1", entry_id)
            raise ValueError("Voce non trovata")
        # Aggiorna anche il backup
        for entry in self.data["partition2"]:
            if entry["id"] == entry_id:
                entry["service"] = enc_service_backup
                entry["username"] = enc_username_backup
                entry["password"] = enc_password_backup
                break
        self.save()
        logger.info("Password entry with id %d updated", entry_id)

    def delete_password(self, entry_id: int):
        """
        Elimina una voce dal database.
        """
        orig_len = len(self.data["partition1"])
        self.data["partition1"] = [entry for entry in self.data["partition1"] if entry["id"] != entry_id]
        self.data["partition2"] = [entry for entry in self.data["partition2"] if entry["id"] != entry_id]
        if len(self.data["partition1"]) == orig_len:
            logger.error("Entry with id %d not found for deletion", entry_id)
            raise ValueError("Voce non trovata")
        self.save()
        logger.info("Password entry with id %d deleted", entry_id)

    def get_passwords(self, partition: int) -> List[Dict[str, Any]]:
        """
        Ottiene tutte le voci da una partizione specifica.
        """
        if partition == 1:
            return self.data["partition1"]
        elif partition == 2:
            return self.data["partition2"]
        else:
            return []

    def update_master_verification(self, enc_verification: str):
        """
        Aggiorna il campo di verifica della Master Password.
        """
        self.data["master_verification"] = enc_verification
        self.save()
        logger.info("Master verification updated.")

    def update_salts(self, main_salt: bytes, backup_salt: bytes):
        """
        Aggiorna i sali utilizzati per la derivazione delle chiavi.
        """
        self.data["main_salt"] = main_salt.hex()
        self.data["backup_salt"] = backup_salt.hex()
        self.save()
        logger.info("Salts updated.")

# ----------------------------
# Dialog per l'aggiornamento delle credenziali
# ----------------------------

class UpdateDialog(QDialog):
    """
    Finestra di dialogo per aggiornare una voce esistente.
    """
    def __init__(self, service: str, username: str, password: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aggiorna Password")
        self.layout = QVBoxLayout()

        self.service_label = QLabel("Service:")
        self.layout.addWidget(self.service_label)
        self.service_input = QLineEdit()
        self.service_input.setText(service)
        self.layout.addWidget(self.service_input)

        self.username_label = QLabel("Username:")
        self.layout.addWidget(self.username_label)
        self.username_input = QLineEdit()
        self.username_input.setText(username)
        self.layout.addWidget(self.username_input)

        self.password_label = QLabel("Password:")
        self.layout.addWidget(self.password_label)
        self.password_input = QLineEdit()
        self.password_input.setText(password)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.layout.addWidget(self.password_input)

        # Bottone per generare una nuova password
        self.generate_button = QPushButton("Genera Password")
        self.generate_button.clicked.connect(self.generate_password)
        self.layout.addWidget(self.generate_button)

        # Pulsanti Salva e Annulla
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Salva")
        self.save_button.clicked.connect(self.accept)
        button_layout.addWidget(self.save_button)
        self.cancel_button = QPushButton("Annulla")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(button_layout)

        self.setLayout(self.layout)

    def generate_password(self):
        """
        Genera una nuova password casuale e la imposta nel campo di input.
        """
        new_pass = generate_password()
        self.password_input.setText(new_pass)

    def get_data(self):
        """
        Restituisce i dati inseriti dall'utente.
        """
        return (self.service_input.text(), self.username_input.text(), self.password_input.text())

# ----------------------------
# Dialog per la Guida con scrollbar
# ----------------------------

class HelpDialog(QDialog):
    """
    Finestra di dialogo per visualizzare la guida dettagliata.
    """
    def __init__(self, help_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help - Guida Dettagliata")
        self.resize(600, 400)
        layout = QVBoxLayout()

        self.text_browser = QTextBrowser()
        self.text_browser.setHtml(help_text)
        layout.addWidget(self.text_browser)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

# ----------------------------
# Interfaccia Utente
# ----------------------------

class PasswordManagerUI(QMainWindow):
    """
    Interfaccia utente principale del Password Manager.
    """
    def __init__(self):
        super().__init__()

        # Inizializza il database persistente (salvato in db.json)
        self.db = PersistentDatabase("db.json")
        self.master_password = None  # Non viene memorizzata in chiaro
        self.key_main = None  # Chiave per Partition 1
        self.key_backup = None  # Chiave per Partition 2

        self.setWindowTitle("Password Manager (Persistenza Encrypted)")
        self.setGeometry(100, 100, 800, 600)

        self.layout = QVBoxLayout()

        # Selettore di partizione
        self.partition_label = QLabel("Seleziona Partizione:")
        self.layout.addWidget(self.partition_label)
        self.partition_selector = QComboBox()
        self.partition_selector.addItems(["Partition 1 (Protetta)", "Partition 2 (Backup)"])
        self.layout.addWidget(self.partition_selector)

        # Input per il service
        self.service_label = QLabel("Service:")
        self.layout.addWidget(self.service_label)
        self.service_input = QLineEdit()
        self.layout.addWidget(self.service_input)

        # Input per lo username
        self.username_label = QLabel("Username:")
        self.layout.addWidget(self.username_label)
        self.username_input = QLineEdit()
        self.layout.addWidget(self.username_input)

        # Input per la password, pulsante per generarla e pulsante per mostrare/nascondere la password
        self.password_label = QLabel("Password:")
        self.layout.addWidget(self.password_label)
        password_layout = QHBoxLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(self.password_input)
        self.generate_button = QPushButton("Genera Password")
        self.generate_button.clicked.connect(self.handle_generate_password)
        password_layout.addWidget(self.generate_button)
        self.toggle_password_button = QPushButton("Mostra")
        self.toggle_password_button.setFixedWidth(60)
        self.toggle_password_button.clicked.connect(self.toggle_password_visibility)
        password_layout.addWidget(self.toggle_password_button)
        self.layout.addLayout(password_layout)

        # Bottone per aggiungere una nuova password (operazione su Partition 1 e backup aggiornato)
        self.add_button = QPushButton("Aggiungi Password (Partition 1)")
        self.add_button.clicked.connect(self.add_password)
        self.layout.addWidget(self.add_button)

        # Bottone per visualizzare le password salvate
        self.view_button = QPushButton("Visualizza Password")
        self.view_button.clicked.connect(self.view_passwords)
        self.layout.addWidget(self.view_button)

        # Tabella per visualizzare le password
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Service", "Username", "Password"])
        self.layout.addWidget(self.table)

        # Bottone per aggiornare la password selezionata
        self.update_button = QPushButton("Aggiorna Password Selezionata (Partition 1)")
        self.update_button.clicked.connect(self.update_selected_password)
        self.layout.addWidget(self.update_button)

        # Bottone per eliminare la password selezionata
        self.delete_button = QPushButton("Elimina Password Selezionata (Partition 1)")
        self.delete_button.clicked.connect(self.delete_selected_password)
        self.layout.addWidget(self.delete_button)

        # Bottone per copiare la password selezionata negli appunti
        self.copy_button = QPushButton("Copia Password Selezionata")
        self.copy_button.clicked.connect(self.copy_selected_password)
        self.layout.addWidget(self.copy_button)

        # Operazioni relative alla Master Password
        self.set_master_password_button = QPushButton("Imposta Master Password")
        self.set_master_password_button.clicked.connect(self.set_master_password)
        self.layout.addWidget(self.set_master_password_button)

        self.change_master_password_button = QPushButton("Cambia Master Password")
        self.change_master_password_button.clicked.connect(self.change_master_password)
        self.layout.addWidget(self.change_master_password_button)

        self.lock_button = QPushButton("Blocca App")
        self.lock_button.clicked.connect(self.lock_app)
        self.layout.addWidget(self.lock_button)

        self.unlock_button = QPushButton("Sblocca App")
        self.unlock_button.clicked.connect(self.unlock_app)
        self.layout.addWidget(self.unlock_button)

        # Bottone Help
        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self.show_help)
        self.layout.addWidget(self.help_button)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

        # Timer per auto-lock dopo 5 minuti di inattività
        self.inactivity_timer = QTimer()
        self.inactivity_timer.setInterval(5 * 60 * 1000)  # 5 minuti
        self.inactivity_timer.timeout.connect(self.lock_app)
        self.inactivity_timer.start()

        # Installo un event filter per resettare il timer ad ogni interazione
        self.installEventFilter(self)

    def eventFilter(self, source, event):
        """
        Resetta il timer di inattività ad ogni interazione dell'utente.
        """
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress):
            self.reset_inactivity_timer()
        return super().eventFilter(source, event)

    def reset_inactivity_timer(self):
        """
        Riavvia il timer di inattività.
        """
        self.inactivity_timer.start()

    def toggle_password_visibility(self):
        """
        Alterna la visibilità della password nel campo di input.
        """
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_password_button.setText("Nascondi")
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_password_button.setText("Mostra")

    def set_master_password(self):
        """
        Imposta la Master Password e deriva le chiavi per la crittografia.
        """
        if self.master_password is not None:
            QMessageBox.information(self, "Info", "La Master Password è già stata impostata per questa sessione.")
            return
        master_password, ok = QInputDialog.getText(
            self, "Master Password", "Inserisci Master Password:", QLineEdit.EchoMode.Password
        )
        if ok and master_password:
            try:
                main_salt = bytes.fromhex(self.db.data["main_salt"])
                backup_salt = bytes.fromhex(self.db.data["backup_salt"])
                key_main = derive_key(master_password, main_salt)
                key_backup = derive_key(master_password, backup_salt)
                # Se è già presente una verifica, la controlla; altrimenti la imposta
                if self.db.data["master_verification"]:
                    stored_ver = bytes.fromhex(self.db.data["master_verification"])
                    if decrypt_data(stored_ver, key_main) != "master_check":
                        QMessageBox.critical(self, "Errore", "Master Password errata.")
                        return
                else:
                    ver_encrypted = encrypt_data("master_check", key_main).hex()
                    self.db.update_master_verification(ver_encrypted)
                self.master_password = master_password
                self.key_main = key_main
                self.key_backup = key_backup
                logger.info("Master password set successfully.")
                QMessageBox.information(self, "Successo", "Master Password impostata correttamente.")
            except Exception as e:
                logger.exception("Error setting master password")
                QMessageBox.critical(self, "Errore", f"Errore nell'impostazione della Master Password: {str(e)}")

    def handle_generate_password(self):
        """
        Genera una nuova password casuale e la imposta nel campo di input.
        """
        new_password = generate_password()
        self.password_input.setText(new_password)
        logger.info("Generated new password.")

    def add_password(self):
        """
        Aggiunge una nuova password al database.
        """
        if not self.key_main or not self.key_backup:
            QMessageBox.warning(self, "Attenzione", "Imposta prima la Master Password.")
            return

        service = self.service_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not service or not username or not password:
            QMessageBox.warning(self, "Attenzione", "Tutti i campi devono essere compilati.")
            return

        try:
            # Cripta separatamente per la partizione principale e il backup
            enc_service_main = encrypt_data(service, self.key_main).hex()
            enc_username_main = encrypt_data(username, self.key_main).hex()
            enc_password_main = encrypt_data(password, self.key_main).hex()

            enc_service_backup = encrypt_data(service, self.key_backup).hex()
            enc_username_backup = encrypt_data(username, self.key_backup).hex()
            enc_password_backup = encrypt_data(password, self.key_backup).hex()

            self.db.add_password(enc_service_main, enc_username_main, enc_password_main,
                                 enc_service_backup, enc_username_backup, enc_password_backup)
            logger.info("Password added for service: %s", service)
            QMessageBox.information(self, "Successo", "Password aggiunta e backup aggiornato.")
            self.service_input.clear()
            self.username_input.clear()
            self.password_input.clear()
        except Exception as e:
            logger.exception("Error adding password")
            QMessageBox.critical(self, "Errore", f"Errore durante l'aggiunta della password: {str(e)}")

    def view_passwords(self):
        """
        Visualizza le password salvate in una tabella.
        """
        if not self.key_main:
            QMessageBox.warning(self, "Attenzione", "Imposta prima la Master Password.")
            return

        partition = 1 if self.partition_selector.currentText().startswith("Partition 1") else 2
        try:
            entries = self.db.get_passwords(partition)
            self.table.setRowCount(0)
            for row_idx, entry in enumerate(entries):
                self.table.insertRow(row_idx)
                self.table.setItem(row_idx, 0, QTableWidgetItem(str(entry["id"])))
                try:
                    key = self.key_main if partition == 1 else self.key_backup
                    service = decrypt_data(bytes.fromhex(entry["service"]), key)
                except Exception:
                    service = "Errore decrittazione"
                self.table.setItem(row_idx, 1, QTableWidgetItem(service))
                try:
                    key = self.key_main if partition == 1 else self.key_backup
                    username = decrypt_data(bytes.fromhex(entry["username"]), key)
                except Exception:
                    username = "Errore decrittazione"
                self.table.setItem(row_idx, 2, QTableWidgetItem(username))
                try:
                    key = self.key_main if partition == 1 else self.key_backup
                    password = decrypt_data(bytes.fromhex(entry["password"]), key)
                except Exception:
                    password = "Errore decrittazione"
                self.table.setItem(row_idx, 3, QTableWidgetItem(password))
            logger.info("Passwords viewed for partition %d", partition)
        except Exception as e:
            logger.exception("Error viewing passwords")
            QMessageBox.critical(self, "Errore", f"Errore durante la visualizzazione: {str(e)}")

    def update_selected_password(self):
        """
        Aggiorna la password selezionata nella tabella.
        """
        if not self.key_main or not self.key_backup:
            QMessageBox.warning(self, "Attenzione", "Imposta prima la Master Password.")
            return

        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Attenzione", "Seleziona una riga da aggiornare.")
            return

        row = selected_items[0].row()
        id_item = self.table.item(row, 0)
        service_item = self.table.item(row, 1)
        username_item = self.table.item(row, 2)
        password_item = self.table.item(row, 3)

        if not (id_item and service_item and username_item and password_item):
            QMessageBox.warning(self, "Attenzione", "Seleziona una riga valida.")
            return

        entry_id = int(id_item.text())
        current_service = service_item.text()
        current_username = username_item.text()
        current_password = password_item.text()

        dialog = UpdateDialog(current_service, current_username, current_password, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_service, new_username, new_password = dialog.get_data()
            if not new_service or not new_username or not new_password:
                QMessageBox.warning(self, "Attenzione", "Tutti i campi devono essere compilati.")
                return
            try:
                enc_service_main = encrypt_data(new_service, self.key_main).hex()
                enc_username_main = encrypt_data(new_username, self.key_main).hex()
                enc_password_main = encrypt_data(new_password, self.key_main).hex()
                enc_service_backup = encrypt_data(new_service, self.key_backup).hex()
                enc_username_backup = encrypt_data(new_username, self.key_backup).hex()
                enc_password_backup = encrypt_data(new_password, self.key_backup).hex()
                self.db.update_password(entry_id, enc_service_main, enc_username_main, enc_password_main,
                                        enc_service_backup, enc_username_backup, enc_password_backup)
                logger.info("Password entry with id %d updated", entry_id)
                QMessageBox.information(self, "Successo", "Password aggiornata e backup sincronizzato.")
                self.view_passwords()
            except Exception as e:
                logger.exception("Error updating password")
                QMessageBox.critical(self, "Errore", f"Errore durante l'aggiornamento: {str(e)}")

    def delete_selected_password(self):
        """
        Elimina la password selezionata nella tabella.
        """
        if not self.key_main or not self.key_backup:
            QMessageBox.warning(self, "Attenzione", "Imposta prima la Master Password.")
            return

        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Attenzione", "Seleziona una riga da eliminare.")
            return

        row = selected_items[0].row()
        id_item = self.table.item(row, 0)
        if not id_item:
            QMessageBox.warning(self, "Attenzione", "Seleziona una riga valida.")
            return

        entry_id = int(id_item.text())
        reply = QMessageBox.question(
            self,
            "Conferma Eliminazione",
            "Sei sicuro di voler eliminare la password selezionata? (Operazione su Partition 1 e backup)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.delete_password(entry_id)
                logger.info("Password entry with id %d deleted", entry_id)
                QMessageBox.information(self, "Successo", "Password eliminata e backup aggiornato.")
                self.view_passwords()
            except Exception as e:
                logger.exception("Error deleting password")
                QMessageBox.critical(self, "Errore", f"Errore durante l'eliminazione: {str(e)}")

    def copy_selected_password(self):
        """
        Copia la password selezionata negli appunti.
        """
        if not self.key_main or not self.key_backup:
            QMessageBox.warning(self, "Attenzione", "Imposta prima la Master Password.")
            return

        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Attenzione", "Seleziona una riga da cui copiare la password.")
            return

        row = selected_items[0].row()
        password_item = self.table.item(row, 3)
        if not password_item:
            QMessageBox.warning(self, "Attenzione", "Seleziona una riga valida.")
            return

        password = password_item.text()
        clipboard: QClipboard = QApplication.clipboard()
        clipboard.setText(password)
        logger.info("Password copied to clipboard.")
        QMessageBox.information(self, "Successo", "Password copiata negli appunti.")

    def re_encrypt_database(self, old_key_main, new_key_main, old_key_backup, new_key_backup):
        """
        Re-cripta tutte le voci del database utilizzando le nuove chiavi.
        """
        try:
            for entry in self.db.data["partition1"]:
                dec_service = decrypt_data(bytes.fromhex(entry["service"]), old_key_main)
                dec_username = decrypt_data(bytes.fromhex(entry["username"]), old_key_main)
                dec_password = decrypt_data(bytes.fromhex(entry["password"]), old_key_main)
                entry["service"] = encrypt_data(dec_service, new_key_main).hex()
                entry["username"] = encrypt_data(dec_username, new_key_main).hex()
                entry["password"] = encrypt_data(dec_password, new_key_main).hex()

            for entry in self.db.data["partition2"]:
                dec_service = decrypt_data(bytes.fromhex(entry["service"]), old_key_backup)
                dec_username = decrypt_data(bytes.fromhex(entry["username"]), old_key_backup)
                dec_password = decrypt_data(bytes.fromhex(entry["password"]), old_key_backup)
                entry["service"] = encrypt_data(dec_service, new_key_backup).hex()
                entry["username"] = encrypt_data(dec_username, new_key_backup).hex()
                entry["password"] = encrypt_data(dec_password, new_key_backup).hex()
            logger.info("Database re-encrypted successfully.")
        except Exception as e:
            logger.exception("Error re-encrypting database entries.")
            raise e

    def change_master_password(self):
        """
        Cambia la Master Password e re-cripta il database con le nuove chiavi.
        """
        if not self.key_main or not self.key_backup:
            QMessageBox.warning(self, "Attenzione", "Imposta prima la Master Password.")
            return

        # Verifica la Master Password corrente
        current_pass, ok = QInputDialog.getText(
            self, "Verifica", "Inserisci la corrente Master Password:", QLineEdit.EchoMode.Password
        )
        if not ok or not current_pass:
            return

        try:
            main_salt = bytes.fromhex(self.db.data["main_salt"])
            key_main_current = derive_key(current_pass, main_salt)
            stored_ver = bytes.fromhex(self.db.data["master_verification"])
            if decrypt_data(stored_ver, key_main_current) != "master_check":
                QMessageBox.critical(self, "Errore", "Master Password corrente errata.")
                return
        except Exception as e:
            logger.exception("Error verifying current master password")
            QMessageBox.critical(self, "Errore", f"Errore durante la verifica: {str(e)}")
            return

        # Richiedi la nuova Master Password
        new_pass, ok = QInputDialog.getText(
            self, "Nuova Master Password", "Inserisci la nuova Master Password:", QLineEdit.EchoMode.Password
        )
        if not ok or not new_pass:
            return

        new_pass_confirm, ok = QInputDialog.getText(
            self, "Conferma", "Conferma la nuova Master Password:", QLineEdit.EchoMode.Password
        )
        if not ok or new_pass != new_pass_confirm:
            QMessageBox.warning(self, "Attenzione", "Le nuove password non coincidono.")
            return

        try:
            # Genera nuovi sali e derivi le nuove chiavi
            new_main_salt = os.urandom(16)
            new_backup_salt = os.urandom(16)
            new_key_main = derive_key(new_pass, new_main_salt)
            new_key_backup = derive_key(new_pass, new_backup_salt)
            # Re-cripta la master verification
            new_ver_encrypted = encrypt_data("master_check", new_key_main).hex()

            # Re-encripta tutte le voci nel database usando una funzione modulare
            self.re_encrypt_database(self.key_main, new_key_main, self.key_backup, new_key_backup)

            # Aggiorna i sali e la master verification nel database
            self.db.update_salts(new_main_salt, new_backup_salt)
            self.db.update_master_verification(new_ver_encrypted)
            self.master_password = new_pass
            self.key_main = new_key_main
            self.key_backup = new_key_backup
            self.db.save()
            logger.info("Master password changed successfully.")
            QMessageBox.information(self, "Successo", "Master Password aggiornata con successo.")
        except Exception as e:
            logger.exception("Error updating master password")
            QMessageBox.critical(self, "Errore", f"Errore durante l'aggiornamento della Master Password: {str(e)}")

    def lock_app(self):
        """
        Blocca l'app cancellando Master Password e chiavi dalla memoria.
        """
        self.master_password = None
        self.key_main = None
        self.key_backup = None
        logger.info("App locked.")
        QMessageBox.information(self, "Bloccato", "L'app è stata bloccata per inattività o manualmente.\nPer sbloccarla, inserisci la Master Password.")

    def unlock_app(self):
        """
        Sblocca l'app richiedendo la Master Password.
        """
        if self.master_password is not None:
            return  # L'app è già sbloccata
        master_password, ok = QInputDialog.getText(
            self, "Sblocca App", "Inserisci la Master Password per sbloccare l'app:", QLineEdit.EchoMode.Password
        )
        if ok and master_password:
            try:
                main_salt = bytes.fromhex(self.db.data["main_salt"])
                backup_salt = bytes.fromhex(self.db.data["backup_salt"])
                key_main = derive_key(master_password, main_salt)
                key_backup = derive_key(master_password, backup_salt)
                stored_ver = bytes.fromhex(self.db.data["master_verification"])
                if decrypt_data(stored_ver, key_main) != "master_check":
                    QMessageBox.critical(self, "Errore", "Master Password errata.")
                    return
                self.master_password = master_password
                self.key_main = key_main
                self.key_backup = key_backup
                logger.info("App unlocked.")
                QMessageBox.information(self, "Successo", "App sbloccata.")
            except Exception as e:
                logger.exception("Error unlocking app")
                QMessageBox.critical(self, "Errore", f"Errore durante lo sblocco: {str(e)}")

    def show_help(self):
        """
        Mostra una finestra di dialogo con la guida dettagliata dell'applicazione.
        """
        help_text = """
        <h2>Guida al Password Manager</h2>
        <p>
            Benvenuto nel Password Manager, un'applicazione progettata per garantire la massima sicurezza nella gestione delle tue credenziali.
            Di seguito troverai una guida dettagliata su come funziona l'app e cosa accade in ogni fase.
        </p>
        <h3>1. Architettura dei Dati e Sicurezza</h3>
        <ul>
            <li><strong>Crittografia:</strong> Tutti i dati (service, username, password) sono criptati usando AES-GCM, che garantisce sia la confidenzialità che l'integrità dei dati.</li>
            <li><strong>Derivazione delle Chiavi:</strong> La tua Master Password non viene mai memorizzata in chiaro. Viene utilizzata per derivare due chiavi separate tramite Argon2:
                <ul>
                    <li><em>Key Main:</em> Utilizzata per criptare i dati nella <strong>Partition 1</strong> (ambiente protetto).</li>
                    <li><em>Key Backup:</em> Utilizzata per criptare i dati nella <strong>Partition 2</strong> (backup dei dati).</li>
                </ul>
            </li>
            <li><strong>Sali (Salts):</strong> Ogni partizione utilizza un salt unico per la derivazione della chiave, aumentando la sicurezza contro attacchi di forza bruta.</li>
        </ul>
        <h3>2. Funzionalità Principali</h3>
        <ul>
            <li><strong>Aggiungi Password:</strong>
                <ul>
                    <li>Inserisci il service, l'username e la password.</li>
                    <li>I dati vengono criptati separatamente per la partizione principale e per il backup.</li>
                    <li>Viene assegnato un ID univoco alla voce, e il backup viene aggiornato simultaneamente.</li>
                </ul>
            </li>
            <li><strong>Visualizza Password:</strong>
                <ul>
                    <li>Puoi selezionare quale partizione visualizzare tramite il menu a tendina.</li>
                    <li>I dati vengono decriptati in tempo reale per essere mostrati nella tabella.</li>
                </ul>
            </li>
            <li><strong>Aggiorna/Elimina Password:</strong>
                <ul>
                    <li>Selezionando una riga della tabella potrai aggiornare o eliminare la voce.</li>
                    <li>Le operazioni vengono effettuate su entrambe le partizioni per garantire la consistenza.</li>
                </ul>
            </li>
            <li><strong>Copia Password:</strong>
                <ul>
                    <li>La password decriptata della voce selezionata può essere copiata negli appunti.</li>
                </ul>
            </li>
        </ul>
        <h3>3. Gestione della Master Password</h3>
        <ul>
            <li><strong>Imposta Master Password:</strong>
                <ul>
                    <li>All'avvio, imposta la tua Master Password. Se è già presente una password, l'app la verifica tramite un campo di controllo.</li>
                </ul>
            </li>
            <li><strong>Cambia Master Password:</strong>
                <ul>
                    <li>È possibile cambiare la Master Password. In questo caso, tutte le voci vengono decriptate con la vecchia chiave e ri-criptate con la nuova.</li>
                    <li>Il processo è modulare e gestito da una funzione dedicata, che assicura la corretta gestione delle eccezioni.</li>
                </ul>
            </li>
            <li><strong>Blocca/Sblocca App:</strong>
                <ul>
                    <li>L'app si blocca automaticamente dopo 5 minuti di inattività o manualmente tramite il pulsante "Blocca App".</li>
                    <li>Per sbloccare l'app, dovrai inserire nuovamente la Master Password.</li>
                </ul>
            </li>
        </ul>
        <h3>4. Meccanismo di Logging</h3>
        <p>
            L'app utilizza un sistema di logging strutturato che registra:
            <ul>
                <li>Eventi di successo (salvataggio del database, aggiunta di nuove voci, cambi di Master Password).</li>
                <li>Errori e eccezioni (problemi di decriptazione, errori di salvataggio, ecc.)</li>
            </ul>
            I log vengono salvati nel file <em>password_manager.log</em> e possono essere consultati per il debug o per tracciare eventuali problemi.
        </p>
        <h3>5. Considerazioni Finali</h3>
        <p>
            Questo Password Manager è progettato per offrire una elevata sicurezza grazie all'uso di crittografia avanzata e una gestione accurata delle chiavi.
            La separazione in due partizioni (una per l'ambiente protetto e una per il backup) offre una ridondanza utile in caso di problemi.
            Assicurati di non condividere la tua Master Password e di tenere al sicuro il file di log per eventuali verifiche.
        </p>
        <p>
            Siamo certi che questa guida ti aiuterà a comprendere ogni aspetto dell'applicazione, dal funzionamento interno alla gestione quotidiana delle tue credenziali.
        </p>
        """
        dialog = HelpDialog(help_text, self)
        dialog.exec()

    def closeEvent(self, event):
        """
        Salva il database e chiude l'applicazione.
        """
        self.db.save()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = PasswordManagerUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()