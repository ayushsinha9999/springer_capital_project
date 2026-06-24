import pandas as pd
import numpy as np

# 1. Define the path to your data folder
data_dir = 'data/'

# 2. Load all CSV files into DataFrames
print("Loading data...")
lead_logs = pd.read_csv(f"{data_dir}lead_log.csv")
paid_transactions = pd.read_csv(f"{data_dir}paid_transactions.csv")
referral_rewards = pd.read_csv(f"{data_dir}referral_rewards.csv")
user_logs = pd.read_csv(f"{data_dir}user_logs.csv")
user_referral_logs = pd.read_csv(f"{data_dir}user_referral_logs.csv")
user_referral_statuses = pd.read_csv(f"{data_dir}user_referral_statuses.csv")
user_referrals = pd.read_csv(f"{data_dir}user_referrals.csv")

# 3. Data Cleaning: Handling Nulls safely
print("Cleaning data...")
# Fill nulls in IDs with empty strings/0 so we don't drop rows needed for fraud detection
user_referrals['transaction_id'] = user_referrals['transaction_id'].fillna('')
user_referrals['referral_reward_id'] = user_referrals['referral_reward_id'].fillna(0)
user_referrals['referee_id'] = user_referrals['referee_id'].fillna('')

# 4. Data Cleaning: String Adjustment (Initcap)
def apply_initcap(df, exclude_cols=[]):
    for col in df.columns:
        # Check if the column is a string type and not an ID or excluded column
        if df[col].dtype == 'object' and col not in exclude_cols and 'id' not in col.lower():
            # Apply title case, keeping original if it's NaN
            df[col] = df[col].apply(lambda x: x.title() if isinstance(x, str) else x)
    return df

# Apply to tables (explicitly excluding 'homeclub' as requested, and timezones)
user_logs = apply_initcap(user_logs, exclude_cols=['homeclub', 'timezone_homeclub'])
user_referrals = apply_initcap(user_referrals)
lead_logs = apply_initcap(lead_logs, exclude_cols=['timezone_location'])
paid_transactions = apply_initcap(paid_transactions, exclude_cols=['timezone_transaction'])

# 5. Data Processing: Source Category mapping
print("Applying business logic for Source Categories...")

# Create a dictionary to map lead_id to source_category quickly
lead_category_map = dict(zip(lead_logs['lead_id'], lead_logs['source_category']))

def get_source_category(row):
    source = row['referral_source']
    if source == 'User Sign Up':
        return 'Online'
    elif source == 'Draft Transaction':
        return 'Offline'
    elif source == 'Lead':
        # When source is Lead, referee_id is actually the lead_id
        return lead_category_map.get(row['referee_id'], 'Unknown')
    return 'Unknown'

# Apply the function to create the new column
user_referrals['referral_source_category'] = user_referrals.apply(get_source_category, axis=1)

# 6. Data Processing: Joins
print("Merging tables...")

# Merge user_referrals with user_referral_logs to get source_transaction_id & reward_granted
# We use a left join because not all referrals have logs yet
merged_df = pd.merge(
    user_referrals, 
    user_referral_logs[['user_referral_id', 'source_transaction_id', 'is_reward_granted', 'created_at']], 
    left_on='referral_id', 
    right_on='user_referral_id', 
    how='left',
    suffixes=('', '_log')
)

# Merge with user_referral_statuses to get the description (Berhasil, etc.)
merged_df = pd.merge(
    merged_df,
    user_referral_statuses[['id', 'description']],
    left_on='user_referral_status_id',
    right_on='id',
    how='left'
).rename(columns={'description': 'referral_status'})

# Merge with referral_rewards to get reward_value
merged_df = pd.merge(
    merged_df,
    referral_rewards[['id', 'reward_value']],
    left_on='referral_reward_id',
    right_on='id',
    how='left',
    suffixes=('', '_reward')
)
# Ensure reward_value is numeric (extract numbers if it says "10 days", or fill 0)
merged_df['reward_value'] = merged_df['reward_value'].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)

# Merge with user_logs to get referrer details (membership, deleted status, timezone)
# We drop duplicates on user_id to avoid creating duplicate rows if user_logs has multiple entries per user
unique_users = user_logs.drop_duplicates(subset=['user_id'])
merged_df = pd.merge(
    merged_df,
    unique_users[['user_id', 'timezone_homeclub', 'membership_expired_date', 'is_deleted', 'homeclub', 'name', 'phone_number']],
    left_on='referrer_id',
    right_on='user_id',
    how='left'
)

# Merge with paid_transactions to get transaction info based on the referral's transaction_id
merged_df = pd.merge(
    merged_df,
    paid_transactions[['transaction_id', 'transaction_status', 'transaction_at', 'transaction_location', 'transaction_type', 'timezone_transaction']],
    on='transaction_id',
    how='left'
)

print(f"Merge complete. Current row count: {len(merged_df)}")

# 7. Data Processing: Timezone Adjustments
print("Adjusting timezones...")
# Convert string timestamps to datetime objects (handling UTC Z at the end)
time_cols = ['referral_at', 'transaction_at', 'created_at_log', 'updated_at']
for col in time_cols:
    merged_df[col] = pd.to_datetime(merged_df[col], format='ISO8601', errors='coerce', utc=True)

# Helper function to convert timezone safely row by row
def convert_to_local(row, time_col, tz_col_1, tz_col_2=None):
    if pd.isnull(row[time_col]):
        return row[time_col]
    
    # Prioritize transaction timezone, then homeclub timezone
    tz = row.get(tz_col_1)
    if pd.isnull(tz) and tz_col_2:
        tz = row.get(tz_col_2)
        
    if pd.isnull(tz):
        tz = 'UTC' # Fallback
        
    try:
        # Convert the UTC time to the target timezone, then remove the tz awareness for clean output
        return row[time_col].tz_convert(tz).tz_localize(None)
    except Exception:
        return row[time_col].tz_localize(None)

# Apply timezone conversions
merged_df['referral_at_local'] = merged_df.apply(lambda row: convert_to_local(row, 'referral_at', 'timezone_transaction', 'timezone_homeclub'), axis=1)
merged_df['transaction_at_local'] = merged_df.apply(lambda row: convert_to_local(row, 'transaction_at', 'timezone_transaction', 'timezone_homeclub'), axis=1)
merged_df['updated_at_local'] = merged_df.apply(lambda row: convert_to_local(row, 'updated_at', 'timezone_transaction', 'timezone_homeclub'), axis=1)
merged_df['reward_granted_at_local'] = merged_df.apply(lambda row: convert_to_local(row, 'created_at_log', 'timezone_transaction', 'timezone_homeclub'), axis=1)

print("Timezone adjustments complete!\n")
# 8. Basic Business Logic: Fraud Detection
print("Evaluating fraud detection logic...")

# Convert membership date to datetime for accurate comparison
merged_df['membership_expired_date'] = pd.to_datetime(merged_df['membership_expired_date'], errors='coerce')

# --- Condition 1 Checks (Valid Referrals) ---
has_reward = merged_df['reward_value'] > 0
status_success = merged_df['referral_status'] == 'Berhasil'
has_txn = merged_df['transaction_id'] != ''
txn_paid = merged_df['transaction_status'].str.upper() == 'PAID'
txn_new = merged_df['transaction_type'].str.upper() == 'NEW'

# Date comparisons (ensuring both sides are timezone-naive for Pandas)
txn_after_ref = merged_df['transaction_at_local'] > merged_df['referral_at_local']
same_month = merged_df['transaction_at_local'].dt.to_period('M') == merged_df['referral_at_local'].dt.to_period('M')
membership_valid = merged_df['membership_expired_date'].dt.tz_localize(None) >= merged_df['referral_at_local'].dt.tz_localize(None)

# Boolean conversions for strict flag checking
acct_not_deleted = ~merged_df['is_deleted'].astype(str).str.lower().isin(['true', '1'])
reward_granted = merged_df['is_reward_granted'].astype(str).str.lower().isin(['true', '1'])

# Combine all 10 rules for Valid Condition 1
valid_cond_1 = (has_reward & status_success & has_txn & txn_paid & 
                txn_new & txn_after_ref & same_month & membership_valid & 
                acct_not_deleted & reward_granted)

# --- Condition 2 Checks (Valid Pending/Failed Referrals) ---
status_pending_failed = merged_df['referral_status'].isin(['Menunggu', 'Tidak Berhasil'])
no_reward = merged_df['reward_value'] == 0
valid_cond_2 = status_pending_failed & no_reward

# Final Validity Column
merged_df['is_business_logic_valid'] = valid_cond_1 | valid_cond_2

# 9. Output Generation
print("Generating final report...")

# Map everything to match the exact requested output schema from the prompt
final_cols = {
    'id': 'referral_details_id',
    'referral_id': 'referral_id',
    'referral_source': 'referral_source',
    'referral_source_category': 'referral_source_category',
    'referral_at_local': 'referral_at',
    'referrer_id': 'referrer_id',
    'name': 'referrer_name',
    'phone_number': 'referrer_phone_number',
    'homeclub': 'referrer_homeclub',
    'referee_id': 'referee_id',
    'referee_name': 'referee_name',
    'referee_phone': 'referee_phone',
    'referral_status': 'referral_status',
    'reward_value': 'num_reward_days',
    'transaction_id': 'transaction_id',
    'transaction_status': 'transaction_status',
    'transaction_at_local': 'transaction_at',
    'transaction_location': 'transaction_location',
    'transaction_type': 'transaction_type',
    'updated_at_local': 'updated_at',
    'reward_granted_at_local': 'reward_granted_at',
    'is_business_logic_valid': 'is_business_logic_valid'
}

# Apply column renaming and exact ordering
final_report = merged_df.rename(columns=final_cols)[list(final_cols.values())]

# Clean up the ID column to be a clean integer
final_report['referral_details_id'] = final_report['referral_details_id'].fillna(0).astype(int)

# Save the final CSV
output_filename = 'final_referral_report.csv'
final_report.to_csv(output_filename, index=False)
print(f"\nBoom! Pipeline finished. Saved {len(final_report)} rows to '{output_filename}'.")