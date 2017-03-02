"""Graphical experiment launcher."""

import sys
from PyQt5.QtWidgets import (
    QApplication, QDialog, QLineEdit, QCheckBox, QComboBox, QLabel, QPushButton,
    QDialogButtonBox, QVBoxLayout, QFormLayout
)


class Launcher(QDialog):
    """For simplicity, this dialog only allows the most common parameters to be
    set, namely subject and experiment, plus simple flags. Overriding
    directories must be done with command line arguments.

    """
    def __init__(self, experiments, args, parent=None):
        super(Launcher, self).__init__(parent=parent)
        vBox = QVBoxLayout()
        form = QFormLayout()

        self.setWindowTitle("Configure task")

        self.subjectBox = QLineEdit(args.get("subject", ""))
        self.subjectBox.textChanged.connect(self.validate_subject)
        form.addRow(QLabel("Subject"), self.subjectBox)

        self.experimentBox = QComboBox()
        self.experimentBox.addItems(sorted(experiments))
        self.experimentBox.setCurrentText(args.get("experiment", ""))
        form.addRow(QLabel("Experiment"), self.experimentBox)

        self.fullscreenBox = QCheckBox("")
        self.fullscreenBox.setChecked(not args["no_fs"])
        form.addRow(QLabel("Fullscreen"), self.fullscreenBox)

        self.okButton = QPushButton("OK")
        self.okButton.setEnabled(False)
        self.dialogButtons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.dialogButtons.addButton(self.okButton, QDialogButtonBox.AcceptRole)
        self.dialogButtons.rejected.connect(self.reject)
        self.dialogButtons.accepted.connect(self.accept)

        vBox.addLayout(form)
        vBox.addWidget(self.dialogButtons)

        self.setLayout(vBox)

        # Ensure OK is clickable if there's a subject
        self.validate_subject()

    def validate_subject(self):
        """Just ensure that there is any text as the subject."""
        self.okButton.setEnabled(len(self.subjectBox.text()) > 0)

    @staticmethod
    def get_updated_args(experiments, args):
        """Entry point to running the launcher dialog to get missing command
        line arguments.

        :param list experiments: List of available experiments.
        :param dict args: Command-line arguments as a dict.
        :returns: Updated command-line arguments based on selections or None
            if canceled.

        """
        app = QApplication(sys.argv)
        dialog = Launcher(experiments, args)
        result = dialog.exec_()
        app.exit(result == QDialog.Accepted)

        args.update({
            "subject": dialog.subjectBox.text(),
            "experiment": dialog.experimentBox.currentText(),
            "no_fs": not dialog.fullscreenBox.isChecked()
        })

        return args if result else None
