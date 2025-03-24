from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle
from PySide6.QtCore import Qt, QRect, QSize, Signal, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QBrush, QPen, QPainterPath, QLinearGradient

class BetDelegate(QStyledItemDelegate):
    customerClicked = Signal(str)  # Signal when customer reference is clicked
    selectionClicked = Signal(str)  # Signal when a selection is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_item = None
        self.hovered_element = None
        self.clickable_areas = {}  # Store clickable regions
        
    def paint(self, painter, option, index):
        # Get the bet data from the model
        bet_dict = index.data(Qt.DisplayRole)
        if not bet_dict:
            return
            
        # Prepare painter
        painter.save()
        
        # Check if item is selected/hovered
        is_selected = option.state & QStyle.State_Selected
        is_hovered = option.state & QStyle.State_MouseOver
        
        # Get risk category for ribbon
        risk_category = bet_dict.get('risk_category', None)
        bet_type = bet_dict.get('type', None)
        
        # Draw the background card with risk ribbon
        self.drawBackground(painter, option, is_selected, is_hovered, risk_category, bet_type)
        
        # Draw the bet content based on type
        if bet_dict['type'] == 'SMS WAGER':
            self.drawSMSWager(painter, option, bet_dict)
        elif bet_dict['type'] == 'WAGER KNOCKBACK':
            self.drawKnockback(painter, option, bet_dict)
        else:
            self.drawRegularBet(painter, option, bet_dict, index.row())
            
        painter.restore()
        
    def drawBackground(self, painter, option, is_selected, is_hovered, customer_risk=None, bet_type=None):
        # Create rounded rectangle for card background
        rect = option.rect.adjusted(5, 3, -5, -3)  # Reduced vertical padding
    
        # Check if the bet is a knockback or SMS
        is_knockback = bet_type == 'WAGER KNOCKBACK'
        is_sms = bet_type == 'SMS WAGER'
        
        # Set background color based on state - darker theme with more subtle accent colors
        if is_selected:
            bg_color = QColor("#333333")  # Darker selected color
        elif is_knockback:
            bg_color = QColor(173, 2, 2, 40)  # More subtle red with transparency
        elif is_sms:
            bg_color = QColor(0, 102, 204, 40)  # More subtle blue with transparency
        elif is_hovered:
            bg_color = QColor("#292929")  # Darker hover color
        else:
            bg_color = QColor("#242424")  # Dark background color
            
        # Draw card with shadow effect
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw shadow (slightly reduced)
        shadow_rect = rect.adjusted(2, 2, 2, 2)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(shadow_rect, 8, 8)
        painter.fillPath(shadow_path, QColor(0, 0, 0, 40))
        
        # Draw card base color
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, bg_color)
        
        # Add gradient overlay for knockbacks and SMS
        if is_knockback or is_sms:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            
            if is_knockback:
                # Subtle red gradient
                gradient.setColorAt(0, QColor(173, 2, 2, 15))
                gradient.setColorAt(1, QColor(173, 2, 2, 40))
                border_color = QColor(173, 2, 2, 80)
            else:  # SMS
                # Subtle blue gradient
                gradient.setColorAt(0, QColor(0, 102, 204, 15))
                gradient.setColorAt(1, QColor(0, 102, 204, 40))
                border_color = QColor(0, 102, 204, 80)
                
            painter.fillPath(path, QBrush(gradient))
            
            # Draw accent border for knockbacks and SMS
            painter.setPen(QPen(border_color, 1))
            painter.drawRoundedRect(rect, 8, 8)
        else:
            # Draw normal border
            painter.setPen(QPen(QColor("#444444"), 1))
            painter.drawRoundedRect(rect, 8, 8)
        
        # Draw the colored ribbon on the left side based on customer risk
        if customer_risk:
            ribbon_width = 5
            ribbon_rect = QRect(rect.left() + 1, rect.top() + 1, ribbon_width, rect.height() - 2)
            
            # Determine ribbon color based on risk/VIP status
            if customer_risk in ('M', 'C'):
                ribbon_color = QColor("#c92a2a")  # Red for risk
            elif customer_risk == 'W':
                ribbon_color = QColor("#e67700")  # Orange for watchlist
            else:
                ribbon_color = QColor("#20c997")  # Green for regular/VIP
                
            ribbon_path = QPainterPath()
            ribbon_path.addRoundedRect(ribbon_rect, 4, 4)
            painter.fillPath(ribbon_path, ribbon_color)

    def drawRegularBet(self, painter, option, bet_dict, row):
        # Extract bet data
        customer_ref = bet_dict.get('customer_ref', '')
        risk_category = bet_dict.get('risk_category', '')
        timestamp = bet_dict.get('time', '')
        bet_no = bet_dict.get('id', '')
        unit_stake = bet_dict.get('unit_stake', 0.0)
        bet_details = bet_dict.get('bet_details', '')
        bet_type = bet_dict.get('bet_type', '')
        
        # Get selections
        selections = []
        if 'selections' in bet_dict and bet_dict['selections'] is not None:
            if isinstance(bet_dict['selections'], list):
                selections = bet_dict['selections']
            else:
                try:
                    import json
                    selections = json.loads(bet_dict['selections'])
                except:
                    selections = []
                    
        # Set up fonts and colors - adjusted for dark theme
        header_font = QFont("Helvetica", 10, QFont.Bold)
        body_font = QFont("Helvetica", 9)
        selection_font = QFont("Helvetica", 9)
            
        # Set all text to white/light colors for dark background
        regular_text_color = QColor("#e0e0e0")  # Light gray for most text
        highlight_text_color = QColor("#ffffff")  # White for important text
        link_color = QColor("#4dabf7")  # Lighter blue for links
                
        # Calculate text rectangles
        rect = option.rect.adjusted(20, 8, -15, -8)  # Increased left padding for ribbon, reduced vertical
        header_rect = QRect(rect.left(), rect.top(), rect.width(), 20)  # Reduced height
        
        # Draw header (Customer ref, risk category, timestamp, bet ID)
        painter.setFont(header_font)
        
        # Save customer ref clickable area
        customer_text = f"{customer_ref} ({risk_category})"
        customer_width = painter.fontMetrics().horizontalAdvance(customer_text)
        customer_rect = QRect(header_rect.left(), header_rect.top(), customer_width, 20)
        self.clickable_areas[f"customer_{row}"] = {
            "rect": customer_rect,
            "data": customer_ref
        }
        
        # Draw customer reference (clickable) - now in white/light color
        painter.setPen(highlight_text_color)
        painter.drawText(customer_rect, Qt.AlignLeft | Qt.AlignVCenter, customer_text)
        
        # Draw timestamp and bet ID
        painter.setPen(regular_text_color)
        timestamp_text = f"{timestamp} - {bet_no}"
        painter.drawText(
            header_rect.left() + customer_width + 10,
            header_rect.top(),
            header_rect.width() - customer_width - 10,
            20,
            Qt.AlignLeft | Qt.AlignVCenter,
            timestamp_text
        )
        
        # Draw bet details
        details_rect = QRect(rect.left(), header_rect.bottom() + 5, rect.width(), 20)
        formatted_stake = f"£{unit_stake:.2f}"
        details_text = f"{formatted_stake} {bet_details}, {bet_type}"
        
        painter.setFont(body_font)
        painter.drawText(details_rect, Qt.AlignLeft | Qt.AlignVCenter, details_text)
        
        # Draw selections
        painter.setFont(selection_font)
        y_offset = details_rect.bottom() + 5
        
        for i, selection in enumerate(selections):
            if not selection or len(selection) < 2:
                continue
                
            selection_text = f"{i+1} - {selection[0]} at {selection[1]}"
            selection_rect = QRect(rect.left() + 15, y_offset, rect.width() - 30, 20)
            
            # Save selection clickable area
            self.clickable_areas[f"selection_{row}_{i}"] = {
                "rect": selection_rect,
                "data": selection[0]
            }
            
            # Draw selection text (clickable)
            painter.setPen(QColor("#0066cc"))
            painter.drawText(selection_rect, Qt.AlignLeft | Qt.AlignVCenter, selection_text)
            
            # Draw underline for clickable selection
            # painter.drawLine(
            #     selection_rect.left(),
            #     selection_rect.bottom(),
            #     selection_rect.left() + painter.fontMetrics().horizontalAdvance(selection[0]) + 2,
            #     selection_rect.bottom()
            # )
            
            y_offset += 20
    
    def drawSMSWager(self, painter, option, bet_dict):
        # Extract bet data
        customer_ref = bet_dict.get('customer_ref', '')
        risk_category = bet_dict.get('risk_category', '')
        timestamp = bet_dict.get('time', '')
        bet_no = bet_dict.get('id', '')
        wager_text = bet_dict.get('details', '')
        
        # Set up fonts
        header_font = QFont("Helvetica", 10, QFont.Bold)
        body_font = QFont("Helvetica", 9)
        
        # Set text colors for dark background
        regular_text_color = QColor("#e0e0e0")  # Light gray for most text
        highlight_text_color = QColor("#ffffff")  # White for important text
        link_color = QColor("#4dabf7")  # Lighter blue for links
        
        # Calculate text rectangles - consistent with regular bets
        rect = option.rect.adjusted(20, 8, -15, -8)  # Increased left padding for ribbon, reduced vertical
        header_rect = QRect(rect.left(), rect.top(), rect.width(), 20)  # Reduced height
        
        # Draw header
        painter.setFont(header_font)
        
        # Save customer ref clickable area
        customer_text = f"{customer_ref} ({risk_category})"
        customer_width = painter.fontMetrics().horizontalAdvance(customer_text)
        customer_rect = QRect(header_rect.left(), header_rect.top(), customer_width, 20)
        row = option.index.row()
        self.clickable_areas[f"customer_{row}"] = {
            "rect": customer_rect,
            "data": customer_ref
        }
        
        # Draw customer reference (clickable)
        painter.setPen(highlight_text_color)
        painter.drawText(customer_rect, Qt.AlignLeft | Qt.AlignVCenter, customer_text)
        
        # Draw timestamp and bet ID
        painter.setPen(regular_text_color)
        timestamp_text = f"{timestamp} - {bet_no}"
        painter.drawText(
            header_rect.left() + customer_width + 10,
            header_rect.top(),
            header_rect.width() - customer_width - 10,
            20,
            Qt.AlignLeft | Qt.AlignVCenter,
            timestamp_text
        )
        
        # Draw SMS wager text
        content_rect = QRect(rect.left(), header_rect.bottom() + 5, rect.width(), rect.height() - 30)
        painter.setFont(body_font)
        painter.setPen(regular_text_color)
        
        # Format the text
        painter.drawText(content_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, str(wager_text))
    
    def drawKnockback(self, painter, option, bet_dict):
        # Extract bet data
        customer_ref = bet_dict.get('customer_ref', '')
        risk_category = bet_dict.get('risk_category', '')
        knockback_id = bet_dict.get('id', '')
        knockback_id = knockback_id.rsplit('-', 1)[0] if '-' in knockback_id else knockback_id
        knockback_details = bet_dict.get('selections', {})
        timestamp = bet_dict.get('time', '')
        error_message = bet_dict.get('error_message', '')
        
        # Set up fonts
        header_font = QFont("Helvetica", 10, QFont.Bold)
        body_font = QFont("Helvetica", 9)
        selection_font = QFont("Helvetica", 9)
        
        # Set text colors for dark background
        regular_text_color = QColor("#e0e0e0")  # Light gray for most text
        highlight_text_color = QColor("#ffffff")  # White for important text
        link_color = QColor("#4dabf7")  # Lighter blue for links
        
        # Calculate text rectangles - consistent with regular bets
        rect = option.rect.adjusted(20, 8, -15, -8)  # Increased left padding for ribbon, reduced vertical
        header_rect = QRect(rect.left(), rect.top(), rect.width(), 20)  # Reduced height
        
        # Draw header
        painter.setFont(header_font)
        
        # Save customer ref clickable area
        customer_text = f"{customer_ref} ({risk_category})"
        customer_width = painter.fontMetrics().horizontalAdvance(customer_text)
        customer_rect = QRect(header_rect.left(), header_rect.top(), customer_width, 20)
        row = option.index.row()
        self.clickable_areas[f"customer_{row}"] = {
            "rect": customer_rect,
            "data": customer_ref
        }
        
        # Draw customer reference (clickable)
        painter.setPen(highlight_text_color)
        painter.drawText(customer_rect, Qt.AlignLeft | Qt.AlignVCenter, customer_text)
        
        # Draw timestamp and bet ID
        painter.setPen(regular_text_color)
        timestamp_text = f"{timestamp} - {knockback_id}"
        painter.drawText(
            header_rect.left() + customer_width + 10,
            header_rect.top(),
            header_rect.width() - customer_width - 10,
            20,
            Qt.AlignLeft | Qt.AlignVCenter,
            timestamp_text
        )
        
        # Process knockback details similar to old code
        formatted_knockback_details = ""
        formatted_selections = ""
        selections = []
        
        # Format the knockback details
        if isinstance(knockback_details, dict):
            formatted_items = []
            # Add all details except for these special keys
            for key, value in knockback_details.items():
                if key not in ['Selections', 'Knockback ID', 'Time', 'Customer Ref', 'Error Message']:
                    formatted_items.append(f'{key}: {value}')
            
            formatted_knockback_details = '\n   '.join(formatted_items)
            
            # Handle selections if present
            if 'Selections' in knockback_details and knockback_details['Selections']:
                selections = knockback_details['Selections']
                selection_items = []
                for selection in selections:
                    if isinstance(selection, dict):
                        meeting = selection.get('- Meeting Name', '')
                        name = selection.get('- Selection Name', '')
                        price = selection.get('- Bet Price', '')
                        selection_items.append(f' - {meeting}, {name}, {price}')
                
                formatted_selections = '\n   '.join(selection_items)
                
        elif isinstance(knockback_details, list):
            # Handle list-style knockback details
            selection_items = []
            selections = knockback_details
            for selection in selections:
                if isinstance(selection, dict):
                    meeting = selection.get('- Meeting Name', '')
                    name = selection.get('- Selection Name', '')
                    price = selection.get('- Bet Price', '')
                    selection_items.append(f' - {meeting}, {name}, {price}')
            
            formatted_selections = '\n   '.join(selection_items)
        
        # Format error message
        if error_message:
            if 'Maximum stake available' in error_message:
                error_message = error_message.replace(', Maximum stake available', '\n   Maximum stake available')
            formatted_error = f"Error Message: {error_message}"
        else:
            formatted_error = ""
        
        # Combine all details
        all_details = formatted_error
        if formatted_knockback_details:
            all_details += ("\n   " if all_details else "") + formatted_knockback_details
        if formatted_selections:
            all_details += ("\n   " if all_details else "") + formatted_selections
        
        # Draw knockback details
        content_rect = QRect(rect.left(), header_rect.bottom() + 5, rect.width(), rect.height() - 30)
        painter.setFont(body_font)
        painter.setPen(regular_text_color)
        
        # Draw the text with word wrap
        painter.drawText(content_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, all_details)
        
        # Make selections clickable if needed
        y_offset = content_rect.top() + painter.fontMetrics().height() * (2 if formatted_error else 1)
        if formatted_knockback_details:
            y_offset += painter.fontMetrics().height() * formatted_knockback_details.count('\n') + 5
        
        # Draw selections as clickable links
        painter.setFont(selection_font)
        for i, selection in enumerate(selections):
            if not isinstance(selection, dict):
                continue
                
            # Get selection name
            selection_name = selection.get('- Selection Name', '')
            if not selection_name:
                continue
            
            # Create clickable area for this selection
            selection_rect = QRect(rect.left() + 15, y_offset, rect.width() - 30, 20)
            self.clickable_areas[f"selection_{row}_{i}"] = {
                "rect": selection_rect,
                "data": selection_name
            }
            
            y_offset += painter.fontMetrics().height()
            
    def sizeHint(self, option, index):
        bet_dict = index.data(Qt.DisplayRole)
        if not bet_dict:
            return QSize(200, 70)
            
        # Calculate height based on content
        height = 55  # Base height for header and details
        
        # Add height for selections
        if bet_dict['type'] != 'SMS WAGER' and 'selections' in bet_dict and bet_dict['selections']:
            selections = []
            if isinstance(bet_dict['selections'], list):
                selections = bet_dict['selections']
            else:
                try:
                    import json
                    selections = json.loads(bet_dict['selections'])
                except:
                    selections = []
                    
            height += len(selections) * 18  # Slightly reduced row height
        
        # For SMS wagers, add height for the SMS text
        if bet_dict['type'] == 'SMS WAGER' and 'text_request' in bet_dict:
            text = bet_dict['text_request']
            if isinstance(text, str):
                height += text.count('\n') * 18 + 15
                
        return QSize(option.rect.width(), height + 20)  # Reduced padding
        
    def editorEvent(self, event, model, option, index):
        # Handle click events on clickable areas
        if event.type() == event.MouseButtonRelease:
            pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            
            for key, area in self.clickable_areas.items():
                if area["rect"].contains(pos):
                    if key.startswith("customer_"):
                        self.customerClicked.emit(area["data"])
                        return True
                    elif key.startswith("selection_"):
                        self.selectionClicked.emit(area["data"])
                        return True
                        
        return super().editorEvent(event, model, option, index)
    
    def set_reference_data(self, oddsmonkey_selections, vip_clients, newreg_clients, reporting_data):
        self.oddsmonkey_selections = oddsmonkey_selections
        self.vip_clients = vip_clients
        self.newreg_clients = newreg_clients
        self.reporting_data = reporting_data
        # Force a repaint if needed
        if self.parent():
            self.parent().viewport().update()

    def get_customer_tag(self, customer_reference, vip_clients, newreg_clients, customer_risk_category=None):
        if customer_reference in vip_clients:
            return "vip"
        elif customer_reference in newreg_clients:
            return "newreg"
        elif customer_risk_category == 'W':
            return "watchlist"
        elif customer_risk_category in ('M', 'C'):
            return "risk"
        else:
            return "default"
        
