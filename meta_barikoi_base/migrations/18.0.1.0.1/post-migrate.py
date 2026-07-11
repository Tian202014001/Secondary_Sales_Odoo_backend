
"""Migration script to remove duplicate menu items from meta_barikoi_base.

The menu items are now defined in meta_barikoi module to avoid duplicates.
"""


def migrate(cr, version):
    """Remove old duplicate menu items from meta_barikoi_base."""
    
    # Delete old menu items that were moved to meta_barikoi module
    # Use proper SQL to avoid JSON field issues
    cr.execute("""
        DELETE FROM ir_ui_menu 
        WHERE id IN (
            SELECT res_id 
            FROM ir_model_data 
            WHERE module = 'meta_barikoi_base' 
            AND model = 'ir.ui.menu'
        )
    """)
    
    # Clean up the ir_model_data entries
    cr.execute("""
        DELETE FROM ir_model_data 
        WHERE module = 'meta_barikoi_base' 
        AND model = 'ir.ui.menu'
    """)
    
    print("Migration: Removed duplicate menu items from meta_barikoi_base")